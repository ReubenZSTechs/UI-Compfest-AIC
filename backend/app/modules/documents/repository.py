# backend/app/modules/documents/repository.py
"""
Persist hasil pemrosesan modular (Tahap 1-5 dari document-parser) ke database
`digital_twin_ingestion` serta pencatatan audit trail ke tabel `document_parse_jobs`.

Disesuaikan agar konsisten dengan Standar Kontrak Data Digital Twin System:
1. Fallback job_descriptions -> job_desks.
2. Worker profile boleh berupa list datar ATAU dict {"workers": [...]}.
3. Compatibility matrix diterima baik dalam bentuk sudah diratakan
   (llm_compatibility_and_evaluations) maupun bentuk mentah bertingkat
   ({worker_id: {jobs: {job_id: {...}}}}); keduanya dinormalisasi ke bentuk flat
   sebelum disimpan.
4. Validasi worker_id pada setiap evaluasi kompatibilitas terhadap daftar worker
   yang valid, untuk mencegah ForeignKeyViolationError di PostgreSQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion.models import (
    Asset,
    CompatibilityEvaluation,
    Factory,
    JobDesk,
    Worker,
)
from app.modules.documents.exceptions import DocumentParserPipelineError
from app.modules.documents.models import DocumentParseJob


def _read_jobs(twin: dict[str, Any]) -> list[dict[str, Any]]:
    """Ekstrak job_desks dengan fallback ke key alternatif 'job_descriptions'."""
    return twin.get("job_desks") or twin.get("job_descriptions") or []


def _unwrap_worker_profile(payload: Any) -> dict[str, Any]:
    """
    Menguraikan payload worker profile menjadi dict ternormalisasi {"workers": [...]}.

    Mendukung ketiga bentuk yang diizinkan Standar Kontrak Data:
    - list datar berisi worker langsung
    - dict {"workers": [...]}
    - dict terbungkus {"worker_profile": {...}} (rekursif)
    """
    data: Any = payload
    while isinstance(data, dict) and "worker_profile" in data:
        data = data["worker_profile"]

    if isinstance(data, list):
        return {"workers": data}

    if isinstance(data, dict):
        workers = data.get("workers", [])
        if isinstance(workers, dict) and "workers" in workers:
            workers = workers["workers"]
        if not isinstance(workers, list):
            workers = []
        return {"workers": workers}

    return {"workers": []}


def _collect_worker_ids(profile_data: dict[str, Any]) -> set[str]:
    """Kumpulkan seluruh worker_id valid -- konsisten dengan service.build_digital_twin_from_results()."""
    ids: set[str] = set()
    for w in profile_data.get("workers", []):
        if not isinstance(w, dict):
            continue
        w_id = w.get("worker_id") or w.get("id") or w.get("worker_code")
        if w_id:
            ids.add(str(w_id))
    return ids


def _flatten_compatibility_matrix(matrix_payload: Any) -> list[dict[str, Any]]:
    """
    Menormalkan payload compatibility matrix ke bentuk flat list
    [{worker_id, job_id, asset_id, evaluations, llm_reasoning}, ...],
    sesuai format `llm_compatibility_and_evaluations` pada Standar Kontrak Data.
    """
    if isinstance(matrix_payload, list):
        return [e for e in matrix_payload if isinstance(e, dict)]

    if not isinstance(matrix_payload, dict):
        return []

    flat = matrix_payload.get("llm_compatibility_and_evaluations")
    if isinstance(flat, list):
        return [e for e in flat if isinstance(e, dict)]

    data: Any = matrix_payload
    while isinstance(data, dict) and isinstance(data.get("compatibility_matrix"), (dict, list)):
        data = data["compatibility_matrix"]

    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]

    if not isinstance(data, dict):
        return []

    flat = data.get("llm_compatibility_and_evaluations")
    if isinstance(flat, list):
        return [e for e in flat if isinstance(e, dict)]

    # Bentuk mentah bertingkat: { worker_id: { jobs: { job_id: {...} } } }
    result: list[dict[str, Any]] = []
    for worker_id, record in data.items():
        if worker_id == "meta" or not isinstance(record, dict):
            continue
        jobs_map = record.get("jobs", {})
        if not isinstance(jobs_map, dict):
            continue
        for job_id, entry in jobs_map.items():
            if not isinstance(entry, dict):
                continue
            result.append(
                {
                    "worker_id": worker_id,
                    "job_id": job_id,
                    "asset_id": entry.get("asset_id"),
                    "evaluations": entry.get("evaluations", {}),
                    "llm_reasoning": entry.get("llm_reasoning", ""),
                }
            )
    return result


async def persist_factory_structure(
    session: AsyncSession, twin: dict[str, Any], warnings: list[str]
) -> str:
    """Tahap 2 -> tabel `factories`, `assets`, dan `job_desks`.
    Melakukan upsert berdasarkan primary key agar re-parse dokumen yang sama
    memperbarui data lama tanpa duplikasi."""
    info = twin.get("factory_info", {})
    factory_id = info["factory_id"]

    factory = await session.get(Factory, factory_id)
    if factory is None:
        factory = Factory(factory_id=factory_id)
        session.add(factory)

    factory.factory_name = info.get("factory_name", factory_id)
    factory.workflow_sequence = info.get("workflow_sequence", [])
    if "process_type" in info:
        factory.process_type = info.get("process_type")
    if "declared_worker_count" in info:
        factory.declared_worker_count = info.get("declared_worker_count")
    if "layout_description" in info:
        factory.layout_description = info.get("layout_description")
    if "parallel_groups" in info:
        factory.parallel_groups = info.get("parallel_groups")

    for asset_data in twin.get("assets", []):
        asset_id = asset_data["asset_id"]
        asset = await session.get(Asset, asset_id)
        if asset is None:
            asset = Asset(asset_id=asset_id)
            session.add(asset)
        asset.factory_id = factory_id
        asset.asset_name = asset_data.get("asset_name", asset_id)
        asset.category = asset_data.get("category", "unknown")
        asset.workflow_step = asset_data.get("workflow_step", "")
        asset.is_automated = bool(asset_data.get("is_automated", False))
        asset.base_throughput_capacity = float(asset_data.get("base_throughput_capacity", 0))
        asset.operational_cost_per_hour = float(asset_data.get("operational_cost_per_hour", 0))
        asset.environmental_factors = asset_data.get("environmental_factors", {})
        asset.metric_derivation_reasoning = asset_data.get("metric_derivation_reasoning", "")
        if "units_available" in asset_data:
            asset.units_available = asset_data.get("units_available")

    for job_data in _read_jobs(twin):
        job_id = job_data["job_id"]
        job = await session.get(JobDesk, job_id)
        if job is None:
            job = JobDesk(job_id=job_id)
            session.add(job)
        job.factory_id = factory_id
        job.job_title = job_data.get("job_title", job_id)
        job.workflow_step = job_data.get("workflow_step", "")
        job.assigned_asset_id = job_data["assigned_asset_id"]
        job.demands = job_data.get("demands", {})
        job.qc_requirement = job_data.get("qc_requirement", "")
        job.metric_derivation_reasoning = job_data.get("metric_derivation_reasoning", "")

    await session.flush()
    return factory_id


async def persist_worker_profile(
    session: AsyncSession, factory_id: str, worker_payload: Any
) -> int:
    """Tahap 4 -> tabel `workers`. Upsert berdasarkan worker_id."""
    profile_data = _unwrap_worker_profile(worker_payload)
    worker_list = profile_data.get("workers", [])

    count = 0
    for worker_data in worker_list:
        if not isinstance(worker_data, dict):
            continue
        worker_id = worker_data.get("worker_id") or worker_data.get("id") or worker_data.get("worker_code")
        if not worker_id:
            continue
        worker_id = str(worker_id)
        worker = await session.get(Worker, worker_id)
        if worker is None:
            worker = Worker(worker_id=worker_id)
            session.add(worker)
        worker.factory_id = factory_id
        worker.name = worker_data.get("name") or worker_id
        worker.demographics = worker_data.get("demographics", {})
        worker.shift_context = worker_data.get("shift_context", {})
        if "skills" in worker_data:
            worker.skills = worker_data.get("skills")
        if "certifications" in worker_data:
            worker.certifications = worker_data.get("certifications")
        if "capabilities" in worker_data:
            worker.capabilities = worker_data.get("capabilities")
        count += 1

    await session.flush()
    return count


async def persist_compatibility_matrix(
    session: AsyncSession,
    factory_id: str,
    matrix_payload: Any,
    valid_worker_ids: set[str] | None = None,
    warnings: list[str] | None = None,
) -> int:
    """Tahap 5 -> tabel `compatibility_evaluations`."""
    await session.execute(
        delete(CompatibilityEvaluation).where(
            CompatibilityEvaluation.factory_id == factory_id
        )
    )

    flat_evals = _flatten_compatibility_matrix(matrix_payload)
    persisted = 0
    for entry in flat_evals:
        worker_id = entry.get("worker_id")
        job_id = entry.get("job_id")
        if not worker_id or not job_id:
            continue
        worker_id = str(worker_id)

        if valid_worker_ids is not None and worker_id not in valid_worker_ids:
            if warnings is not None:
                warnings.append(
                    f"Evaluasi kompatibilitas untuk worker_id '{worker_id}' diabaikan "
                    f"karena worker_id tidak terdaftar pada tabel workers."
                )
            continue

        session.add(
            CompatibilityEvaluation(
                factory_id=factory_id,
                worker_id=worker_id,
                job_id=job_id,
                asset_id=entry.get("asset_id"),
                evaluations=entry.get("evaluations", {}),
                llm_reasoning=entry.get("llm_reasoning", ""),
            )
        )
        persisted += 1

    await session.flush()
    return persisted


async def persist_completed_pipeline(
    session: AsyncSession,
    *,
    factory_structure: dict[str, Any],
    worker_profile: Any,
    compatibility_matrix: Any,
    template_filename: str | None = None,
    cv_bundle_filename: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Menyimpan hasil akhir 5 tahap ke tabel relasional dan merekam audit trail sukses ke `document_parse_jobs`."""
    accumulated_warnings = list(warnings or [])

    factory_id = await persist_factory_structure(
        session, factory_structure, accumulated_warnings
    )

    stored_worker_profile = _unwrap_worker_profile(worker_profile)
    workers_parsed = await persist_worker_profile(session, factory_id, stored_worker_profile)
    valid_worker_ids = _collect_worker_ids(stored_worker_profile)

    stored_compatibility_matrix = {
        "llm_compatibility_and_evaluations": _flatten_compatibility_matrix(compatibility_matrix)
    }
    await persist_compatibility_matrix(
        session,
        factory_id,
        stored_compatibility_matrix,
        valid_worker_ids=valid_worker_ids,
        warnings=accumulated_warnings,
    )

    job_desks_parsed = len(_read_jobs(factory_structure))

    job = DocumentParseJob(
        factory_id=factory_id,
        status="success",
        template_filename=template_filename,
        cv_bundle_filename=cv_bundle_filename,
        workers_parsed=workers_parsed,
        job_desks_parsed=job_desks_parsed,
        warnings=accumulated_warnings,
        error_stage=None,
        error_message=None,
        error_details=None,
        factory_structure=factory_structure,
        worker_profile=stored_worker_profile,
        compatibility_matrix=stored_compatibility_matrix,
        floor_state=None,  # Tahap 6 skipped
    )
    session.add(job)
    await session.commit()

    return {
        "job_id": str(job.id),
        "factory_id": factory_id,
        "workers_parsed": workers_parsed,
        "job_desks_parsed": job_desks_parsed,
        "warnings": accumulated_warnings,
    }


async def persist_combined_pipeline(
    session: AsyncSession,
    combined_result: dict[str, Any],
    template_filename: str | None = None,
    cv_bundle_filename: str | None = None,
) -> dict[str, Any]:
    """Convenience method untuk menyimpan output langsung dari `process_combined_documents_pipeline` (Tahap 1, 2, 4, & 5)."""
    factory_structure = combined_result.get("factory_structure", {})
    worker_profile = combined_result.get("worker_profile", {})
    compatibility_matrix = combined_result.get("compatibility_matrix", {})
    extraction_warnings = combined_result.get("extraction_summary", {}).get("warnings", [])

    return await persist_completed_pipeline(
        session,
        factory_structure=factory_structure,
        worker_profile=worker_profile,
        compatibility_matrix=compatibility_matrix,
        template_filename=template_filename,
        cv_bundle_filename=cv_bundle_filename,
        warnings=extraction_warnings,
    )


async def record_failed_parse_job(
    session: AsyncSession,
    *,
    error: DocumentParserPipelineError,
    template_filename: str | None = None,
    cv_bundle_filename: str | None = None,
    factory_id: str | None = None,
) -> None:
    """Mencatat riwayat kegagalan proses ke `document_parse_jobs`."""
    session.add(
        DocumentParseJob(
            factory_id=factory_id,
            status="error",
            template_filename=template_filename,
            cv_bundle_filename=cv_bundle_filename,
            workers_parsed=0,
            job_desks_parsed=0,
            warnings=[],
            error_stage=error.stage,
            error_message=error.message,
            error_details=error.details or None,
            factory_structure=None,
            worker_profile=None,
            compatibility_matrix=None,
            floor_state=None,
        )
    )
    await session.commit()