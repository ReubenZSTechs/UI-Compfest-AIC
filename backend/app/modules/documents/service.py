"""
backend/app/modules/documents/service.py

Layanan modul document-parser terisolasi (Tahap 1+2 Terpadu, Tahap 4, Tahap 5, & Kombinasi 1-5)
dengan integrasi pencatatan audit log (DocumentParseJob) dan ingestion ke Digital Twin DB.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.modules.digital_twin_ingestion import schemas as dt_schemas
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.modules.documents.models import DocumentParseJob
from app.services.agent_registry_service import AgentRole, get_agent_registry
from app.services.cross_reference_job_worker_service import (
    CompatibilityEvaluationError,
    generate_compatibility_matrix,
)
from app.services.cv_pdf_parser_service import (
    build_worker_agent_input,
)
from app.services.extract_input_field_service import (
    UnsupportedDocumentError,
    build_agent_input,
    extract_document,
)
from app.services.extract_worker_archive_service import (
    ArchiveError,
    extract_worker_uploads,
)

from .exceptions import DocumentParserPipelineError

TEMPLATE_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt"}
WORKER_SUFFIXES = {".zip"}


def _validate_suffix(filename: str, allowed_suffixes: set[str], label: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_suffixes:
        allowed_fmt = ", ".join(sorted(allowed_suffixes))
        raise DocumentParserPipelineError(
            "upload",
            f"{label}: format {suffix or '(tidak ada)'} tidak didukung. Ekstensi yang diizinkan: {allowed_fmt}",
        )


def _to_dict(obj: Any) -> dict[str, Any]:
    """Helper aman untuk mengonversi model Pydantic v1/v2 atau dict ke dict murni."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return {}


def build_digital_twin_from_results(
    factory_structure: Any,
    worker_profile: Any,
    compatibility_matrix: Any,
    warnings: list[str] | None = None,
) -> dt_schemas.DigitalTwin:
    """
    Helper untuk mengonversi hasil parsing mentah (dict atau model Pydantic)
    menjadi skema DigitalTwin Pydantic yang valid.
    
    Menangani fallback penamaan key 'job_descriptions' -> 'job_desks',
    meratakan (flatten) nested compatibility_matrix, serta memvalidasi
    bahwa setiap worker_id pada evaluasi terdaftar di daftar workers
    untuk mencegah ForeignKeyViolationError di PostgreSQL.
    """
    if warnings is None:
        warnings = []

    fac_dict = _to_dict(factory_structure)
    wrk_dict = _to_dict(worker_profile)
    mat_dict = (
        _to_dict(compatibility_matrix)
        if not isinstance(compatibility_matrix, list)
        else {"llm_compatibility_and_evaluations": compatibility_matrix}
    )

    # 1. Ekstraksi Factory Info & Assets
    factory_info_data = fac_dict.get("factory_info", {})
    assets_data = fac_dict.get("assets", [])

    # 2. Ekstraksi Job Desks (Konsistensi Fallback Key)
    job_desks_data = (
        fac_dict.get("job_desks")
        or fac_dict.get("job_descriptions")
        or []
    )

    # 3. Ekstraksi Workers & Penentuan valid_worker_ids
    workers_data = wrk_dict.get("workers", wrk_dict if isinstance(wrk_dict, list) else [])
    if isinstance(workers_data, dict) and "workers" in workers_data:
        workers_data = workers_data["workers"]
    elif isinstance(wrk_dict, dict) and "worker_profile" in wrk_dict:
        inner_wp = wrk_dict["worker_profile"]
        if isinstance(inner_wp, dict):
            workers_data = inner_wp.get("workers", [])
        elif isinstance(inner_wp, list):
            workers_data = inner_wp

    # Kumpulkan seluruh worker_id yang valid
    valid_worker_ids: set[str] = set()
    if isinstance(workers_data, list):
        for w in workers_data:
            w_item = _to_dict(w)
            w_id = w_item.get("worker_id") or w_item.get("id") or w_item.get("worker_code")
            if w_id:
                valid_worker_ids.add(str(w_id))

    # 4. Transformasi & Ekstraksi Matriks Kompatibilitas
    evals_data = mat_dict.get("llm_compatibility_and_evaluations")

    if evals_data is None:
        raw_matrix = mat_dict.get("compatibility_matrix", mat_dict)

        if isinstance(raw_matrix, list):
            evals_data = raw_matrix
        elif isinstance(raw_matrix, dict):
            inner_matrix = raw_matrix.get("compatibility_matrix", raw_matrix)
            evals_list = []
            if isinstance(inner_matrix, dict):
                for worker_id, w_data in inner_matrix.items():
                    if not isinstance(w_data, dict):
                        continue
                    jobs_map = w_data.get("jobs", {})
                    for job_id, j_eval in jobs_map.items():
                        if isinstance(j_eval, dict):
                            evals_list.append({
                                "worker_id": worker_id,
                                "job_id": job_id,
                                "evaluations": j_eval.get("evaluations", {}),
                                "llm_reasoning": j_eval.get("llm_reasoning", "")
                            })
            evals_data = evals_list
        else:
            evals_data = []

    # Validasi & filter evaluasi agar worker_id wajib ada pada valid_worker_ids
    filtered_evals: list[dict[str, Any]] = []
    if isinstance(evals_data, list):
        for ev in evals_data:
            ev_dict = _to_dict(ev)
            e_wid = str(ev_dict.get("worker_id", ""))
            if e_wid and e_wid in valid_worker_ids:
                filtered_evals.append(ev_dict)
            else:
                warnings.append(
                    f"Evaluasi kompatibilitas untuk worker_id '{e_wid}' diabaikan "
                    f"karena worker_id tidak terdaftar pada tabel workers."
                )

    dt_payload = {
        "factory_info": factory_info_data,
        "assets": assets_data,
        "job_desks": job_desks_data,
        "workers": workers_data,
        "llm_compatibility_and_evaluations": filtered_evals,
        "warnings": warnings,
    }

    return dt_schemas.DigitalTwin.model_validate(dt_payload)


# --- Tahap 1 & 2 Terpadu: Ekstraksi Dokumen & Generasi Struktur Pabrik ---

async def process_factory_document_pipeline(
    template: UploadFile,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Menggabungkan Tahap 1 (Ekstraksi Dokumen Pabrik) dan Tahap 2 (Agent A)
    menjadi satu kesatuan alur proses.
    """
    filename = template.filename or "template.pdf"
    _validate_suffix(filename, TEMPLATE_SUFFIXES, "template")

    job: DocumentParseJob | None = None
    if db is not None:
        job = DocumentParseJob(
            status="in_progress",
            template_filename=filename,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    warnings: list[str] = []

    try:
        # 1. Ekstraksi File Dokumen
        with tempfile.TemporaryDirectory(prefix="doc_pipeline_") as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(await template.read())

            try:
                document = await run_in_threadpool(extract_document, tmp_path)
            except UnsupportedDocumentError as error:
                raise DocumentParserPipelineError("extract", str(error)) from error

        # Validasi kelengkapan dokumen mentah
        if len(document.tables) < 3:
            warnings.append(
                f"Dokumen template hanya berisi {len(document.tables)} tabel (diharapkan 3)."
            )

        missing_tables = document.missing_tables()
        if missing_tables:
            warnings.append(
                f"Tabel yang tidak terdeteksi: {', '.join(f'Tabel {t}' for t in missing_tables)}"
            )

        missing_fields = document.missing_text_fields()
        if missing_fields:
            warnings.append(f"Field template belum terbaca: {', '.join(missing_fields)}")

        # 2. Formulasi prompt untuk Agent A
        agent_input = build_agent_input(document)

        # 3. Eksekusi Agent A (Struktur Pabrik)
        registry = get_agent_registry()
        factory_agent = registry.get(AgentRole.FACTORY_STRUCTURE)

        try:
            twin = await run_in_threadpool(
                factory_agent.generate_structured, user_prompt=agent_input
            )
        except Exception as error:
            raise DocumentParserPipelineError(
                "llm_parse", f"Agent struktur pabrik gagal: {error}"
            ) from error

        fac_structure_dict = _to_dict(twin)

        if db is not None and job is not None:
            factory_info = fac_structure_dict.get("factory_info", {})
            parsed_job_desks = (
                fac_structure_dict.get("job_desks")
                or fac_structure_dict.get("job_descriptions")
                or []
            )
            job.status = "success"
            job.factory_id = factory_info.get("factory_id")
            job.job_desks_parsed = len(parsed_job_desks)
            job.warnings = warnings
            job.factory_structure = fac_structure_dict
            await db.commit()
            await db.refresh(job)

        return {
            "parse_job_id": job.id if job else None,
            "extraction_summary": {
                "extracted_fields": document.text_fields,
                "tables_count": len(document.tables),
                "raw_text": document.raw_text,
                "warnings": warnings,
            },
            "agent_input": agent_input,
            "factory_structure": twin,
        }

    except DocumentParserPipelineError as err:
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = err.stage
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception:
                pass
        raise err
    except Exception as err:
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = "unknown"
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception:
                pass
        raise err


# --- Tahap 4: Ekstraksi ZIP CV & Agent B (Profil Pekerja) ---

async def step_4_extract_worker_profiles(
    worker_zip: UploadFile,
    strict: bool = False,
) -> dict[str, Any]:
    """
    Menerima arsip ZIP berisi banyak CV, mengekstraksinya menggunakan
    `extract_worker_uploads`, lalu memanggil Agent B.
    """
    filename = worker_zip.filename or "workers.zip"
    _validate_suffix(filename, WORKER_SUFFIXES, "worker_zip")

    with tempfile.TemporaryDirectory(prefix="worker_step4_") as tmp_dir:
        tmp_path = Path(tmp_dir) / filename
        tmp_path.write_bytes(await worker_zip.read())

        try:
            worker_document, archive_reports = await run_in_threadpool(
                extract_worker_uploads,
                [tmp_path],
                strict=strict,
            )
        except (ArchiveError, UnsupportedDocumentError) as error:
            raise DocumentParserPipelineError("extract", str(error)) from error
        except Exception as error:
            raise DocumentParserPipelineError(
                "extract", f"Gagal mengekstraksi arsip ZIP pekerja: {error}"
            ) from error

        worker_agent_input = build_worker_agent_input(worker_document)

    # Panggil Agent B (WORKER_PROFILE)
    registry = get_agent_registry()
    worker_agent = registry.get(AgentRole.WORKER_PROFILE)

    try:
        worker_profile = await run_in_threadpool(
            worker_agent.generate_structured, user_prompt=worker_agent_input
        )
    except Exception as error:
        raise DocumentParserPipelineError(
            "llm_parse", f"Agent profil pekerja gagal: {error}"
        ) from error

    return {
        "worker_profile": worker_profile,
        "worker_agent_input": worker_agent_input,
        "candidates_found": len(worker_document.candidates),
        "rejected_blocks_count": len(worker_document.rejected_blocks),
        "archive_reports": [
            {
                "archive_name": r.archive_name,
                "accepted_count": r.accepted_count(),
                "skipped": r.skipped,
                "failed": r.failed,
            }
            for r in archive_reports
        ],
    }


# --- Tahap 5: Matriks Kompatibilitas ---

async def step_5_generate_compatibility_matrix(
    factory_structure: dict[str, Any],
    worker_profile: dict[str, Any],
    max_workers: int = 4,
    max_attempts: int = 3,
    strict_compatibility: bool = False,
) -> dict[str, Any]:
    """Memetakan pencocokan job desk pabrik dengan profil pekerja."""
    worker_list = (
        worker_profile.get("workers", [])
        if isinstance(worker_profile, dict)
        else getattr(worker_profile, "workers", [])
    )

    registry = get_agent_registry()
    compatibility_agent = registry.get(AgentRole.WORKER_COMPATIBILITY)

    try:
        matrix = await run_in_threadpool(
            generate_compatibility_matrix,
            factory=factory_structure,
            workers=worker_list,
            agent=compatibility_agent,
            max_workers=max_workers,
            max_attempts=max_attempts,
            strict=strict_compatibility,
        )
    except CompatibilityEvaluationError as error:
        raise DocumentParserPipelineError("compatibility", str(error)) from error
    except Exception as error:
        raise DocumentParserPipelineError(
            "compatibility", f"Gagal membuat matriks kompatibilitas: {error}"
        ) from error

    return {
        "compatibility_matrix": matrix,
        "warnings": [],
    }


# --- Fungsi Kombinasi: Tahap 1+2, Tahap 4, & Tahap 5 (Persisted & Ingested) ---

async def process_combined_documents_pipeline(
    template: UploadFile,
    worker_zip: UploadFile,
    db: AsyncSession | None = None,
    strict: bool = False,
    max_workers: int = 4,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """
    Menggabungkan pemrosesan dokumen pabrik (Tahap 1+2), pemrosesan ZIP CV worker (Tahap 4),
    dan pembentukan matriks kompatibilitas (Tahap 5) dalam satu alur eksekusi sekaligus.
    
    Jika `db` diberikan:
    1. Mencatat audit log `DocumentParseJob`.
    2. Menyimpan data Digital Twin lengkap ke tabel `factories`, `assets`, `job_desks`, `workers`, dll.
    """
    template_filename = template.filename or "template.pdf"
    cv_bundle_filename = worker_zip.filename or "workers.zip"

    job: DocumentParseJob | None = None
    if db is not None:
        job = DocumentParseJob(
            status="in_progress",
            template_filename=template_filename,
            cv_bundle_filename=cv_bundle_filename,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    try:
        # 1. Jalankan Tahap 1 & 2 (Pabrik)
        factory_result = await process_factory_document_pipeline(template)

        # 2. Jalankan Tahap 4 (Pekerja)
        worker_result = await step_4_extract_worker_profiles(worker_zip, strict=strict)

        # 3. Jalankan Tahap 5 (Matriks Kompatibilitas)
        compatibility_result = await step_5_generate_compatibility_matrix(
            factory_structure=factory_result["factory_structure"],
            worker_profile=worker_result["worker_profile"],
            max_workers=max_workers,
            max_attempts=max_attempts,
            strict_compatibility=strict,
        )

        response_payload = {
            "parse_job_id": job.id if job else None,
            # Hasil Pabrik (Tahap 1 & 2)
            "extraction_summary": factory_result["extraction_summary"],
            "agent_input": factory_result["agent_input"],
            "factory_structure": factory_result["factory_structure"],
            # Hasil Worker (Tahap 4)
            "worker_profile": worker_result["worker_profile"],
            "worker_agent_input": worker_result["worker_agent_input"],
            "candidates_found": worker_result["candidates_found"],
            "rejected_blocks_count": worker_result["rejected_blocks_count"],
            "archive_reports": worker_result["archive_reports"],
            # Hasil Kompatibilitas (Tahap 5)
            "compatibility_matrix": compatibility_result["compatibility_matrix"],
        }

        # 4. Ingestion ke Basis Data Digital Twin & Update Audit Log
        if db is not None and job is not None:
            warnings = factory_result["extraction_summary"].get("warnings", [])
            dt_model = build_digital_twin_from_results(
                factory_structure=factory_result["factory_structure"],
                worker_profile=worker_result["worker_profile"],
                compatibility_matrix=compatibility_result["compatibility_matrix"],
                warnings=warnings,
            )

            dt_service = DigitalTwinService(db)
            try:
                # Gunakan savepoint transaksi terisolasi agar kegagalan DB tidak merusak session
                async with db.begin_nested():
                    await dt_service.save_digital_twin(dt_model)
            except Exception as dt_err:
                warnings.append(f"Gagal melakukan ingestion ke Digital Twin DB: {dt_err}")

            # Update audit trail record dengan hasil normalisasi
            job.status = "success"
            job.factory_id = dt_model.factory_info.factory_id
            job.job_desks_parsed = len(dt_model.job_desks)
            job.workers_parsed = len(dt_model.workers)
            job.warnings = warnings
            job.factory_structure = _to_dict(factory_result["factory_structure"])
            job.worker_profile = _to_dict(worker_result["worker_profile"])
            job.compatibility_matrix = _to_dict(compatibility_result["compatibility_matrix"])

            await db.commit()
            await db.refresh(job)

        return response_payload

    except DocumentParserPipelineError as err:
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = err.stage
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception:
                pass
        raise err
    except Exception as err:
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = "unknown"
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception:
                pass
        raise err