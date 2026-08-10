"""
backend/app/modules/documents/repository.py

Persist hasil pemrosesan modular (Tahap 1-5 dari document-parser) ke database
`digital_twin_ingestion` serta pencatatan audit trail ke tabel `document_parse_jobs`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion.models import (
    Asset,
    CompatibilityEvaluation,
    Factory,
    JobDesk,
    Worker,
)

from .exceptions import DocumentParserPipelineError
from .models import DocumentParseJob


def _read_jobs(twin: dict[str, Any]) -> list[dict[str, Any]]:
    return twin.get("job_desks", [])


def _unwrap_worker_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Menguraikan wrapper dict secara rekursif jika payload dibungkus key 'worker_profile'."""
    data = payload
    while isinstance(data, dict) and "worker_profile" in data and isinstance(data["worker_profile"], dict):
        data = data["worker_profile"]
    return data if isinstance(data, dict) else {}


def _unwrap_compatibility_matrix(payload: dict[str, Any]) -> dict[str, Any]:
    """Menguraikan wrapper dict secara rekursif jika payload dibungkus key 'compatibility_matrix'."""
    data = payload
    while (
        isinstance(data, dict)
        and "compatibility_matrix" in data
        and isinstance(data["compatibility_matrix"], dict)
        and "compatibility_matrix" in data["compatibility_matrix"]
    ):
        data = data["compatibility_matrix"]
    return data if isinstance(data, dict) else {}


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
        warnings.append(
            "factory_info.process_type dari Agent A tidak disimpan ke tabel "
            "`factories` (belum ada kolom) -- tersimpan di document_parse_jobs.factory_structure."
        )

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
            warnings.append(
                f"assets.{asset_id}.units_available dari Agent A tidak disimpan ke "
                "tabel `assets` -- tersimpan di document_parse_jobs.factory_structure."
            )

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
    session: AsyncSession, factory_id: str, worker_payload: dict[str, Any]
) -> int:
    """Tahap 4 -> tabel `workers`. Upsert berdasarkan worker_id."""
    profile_data = _unwrap_worker_profile(worker_payload)
    worker_list = profile_data.get("workers", [])
    count = 0

    for worker_data in worker_list:
        if not isinstance(worker_data, dict):
            continue
        worker_id = worker_data.get("worker_id")
        if not worker_id:
            continue

        worker = await session.get(Worker, worker_id)
        if worker is None:
            worker = Worker(worker_id=worker_id)
            session.add(worker)

        worker.factory_id = factory_id
        worker.name = worker_data.get("name") or worker_id
        worker.demographics = worker_data.get("demographics", {})
        worker.shift_context = worker_data.get("shift_context", {})
        count += 1

    await session.flush()
    return count


async def persist_compatibility_matrix(
    session: AsyncSession, factory_id: str, matrix_payload: dict[str, Any]
) -> None:
    """Tahap 5 -> tabel `compatibility_evaluations`.
    Menghapus evaluasi lama untuk pabrik ini lalu menyisipkan ulang seluruh pasangan baru."""
    await session.execute(
        CompatibilityEvaluation.__table__.delete().where(
            CompatibilityEvaluation.factory_id == factory_id
        )
    )

    unwrapped_matrix = _unwrap_compatibility_matrix(matrix_payload)
    target_matrix = unwrapped_matrix.get("compatibility_matrix", unwrapped_matrix)

    for worker_id, record in target_matrix.items():
        if not isinstance(record, dict) or worker_id == "meta":
            continue
        for job_id, entry in record.get("jobs", {}).items():
            if not isinstance(entry, dict):
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

    await session.flush()


async def persist_completed_pipeline(
    session: AsyncSession,
    *,
    factory_structure: dict[str, Any],
    worker_profile: dict[str, Any],
    compatibility_matrix: dict[str, Any],
    template_filename: str | None = None,
    cv_bundle_filename: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Menyimpan hasil akhir 5 tahap ke tabel relasional dan merekam audit trail sukses ke `document_parse_jobs`."""
    accumulated_warnings = list(warnings or [])

    factory_id = await persist_factory_structure(
        session, factory_structure, accumulated_warnings
    )
    workers_parsed = await persist_worker_profile(session, factory_id, worker_profile)
    await persist_compatibility_matrix(session, factory_id, compatibility_matrix)

    job_desks_parsed = len(_read_jobs(factory_structure))
    stored_worker_profile = _unwrap_worker_profile(worker_profile)
    stored_compatibility_matrix = _unwrap_compatibility_matrix(compatibility_matrix)

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
    """Convenience method untuk menyimpan output lansung dari `process_combined_documents_pipeline` (Tahap 1, 2, 4, & 5)."""
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