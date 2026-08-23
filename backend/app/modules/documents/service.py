"""
backend/app/modules/documents/service.py

Layanan modul document-parser terisolasi (Tahap 1+2 Terpadu, Tahap 4, Tahap 5, & Kombinasi 1-5)
dengan integrasi pencatatan audit log (DocumentParseJob) dan ingestion ke Digital Twin DB.

Perubahan pada revisi ini:
1. FIX BUG KRITIS: `job.factory_id` pada `process_combined_documents_pipeline` sebelumnya
   selalu diisi meskipun ingestion ke Digital Twin DB gagal (savepoint di-rollback),
   sehingga menyebabkan ForeignKeyViolationError kedua saat `db.commit()` (factory_id
   menunjuk ke row `factories` yang tidak pernah benar-benar tersimpan). Sekarang
   `factory_id`/`job_desks_parsed`/`workers_parsed` hanya diisi bila ingestion sukses.
2. Ditambahkan logging JSON pretty-printed di setiap tahap pipeline (START/SUCCESS/ERROR)
   untuk mempermudah debugging melalui console/log server.
3. FIX: Menyesuaikan mode ekstraksi dokumen (mendukung Workbook/PDF) secara defensif dengan 
   mengubah variabel `document` menjadi `source` dan mengambil metrik menggunakan `getattr`.
4. FIX: Menambahkan dukungan ekstensi Excel (.xlsx, .xls) dan CSV ke TEMPLATE_SUFFIXES.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import select
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
    build_worker_agent_input_chunks,
    candidate_payload,
)
from app.services.extract_input_field_service import (
    UnsupportedDocumentError,
    build_any_agent_input,
    extract_any,
)
from app.services.extract_xlsx_input_service import UnsupportedWorkbookError

from app.services.extract_worker_archive_service import (
    ArchiveError,
    extract_worker_uploads,
)
from app.services.generate_worker_profiles_service import (
    WorkerProfileGenerationError,
    generate_worker_profiles,
)

from .exceptions import DocumentParserPipelineError

# FIX: Menambahkan ekstensi file Excel dan CSV agar tidak di-reject dengan Error 422
TEMPLATE_SUFFIXES = {".pdf", ".docx", ".md", ".markdown", ".txt", ".xlsx", ".xls", ".csv"}
WORKER_SUFFIXES = {".zip"}


# --------------------------------------------------------------------------
# Utilitas Logging JSON
# --------------------------------------------------------------------------

def _json_safe(value: Any, _depth: int = 0) -> Any:
    """
    Mengonversi value apapun menjadi struktur yang aman untuk di-serialize ke JSON,
    membatasi kedalaman rekursi & ukuran string agar log tidak membanjiri console.
    """
    if _depth > 4:
        return "...(truncated: max depth)"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        return value if len(value) <= 500 else value[:500] + f"...(truncated, total {len(value)} chars)"

    if hasattr(value, "model_dump"):
        try:
            return _json_safe(value.model_dump(), _depth + 1)
        except Exception:
            return str(value)

    if hasattr(value, "dict") and not isinstance(value, type):
        try:
            return _json_safe(value.dict(), _depth + 1)
        except Exception:
            return str(value)

    if isinstance(value, dict):
        return {str(k): _json_safe(v, _depth + 1) for k, v in list(value.items())[:50]}

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        preview = [_json_safe(v, _depth + 1) for v in items[:20]]
        if len(items) > 20:
            preview.append(f"...(truncated, total {len(items)} items)")
        return preview

    return str(value)


def _log_json(step_name: str, status: str, **data: Any) -> None:
    """
    Mencetak log berbasis JSON (pretty-printed) ke console/stdout untuk setiap
    tahapan pipeline, guna mempermudah proses debugging.

    status: "START" | "SUCCESS" | "ERROR"
    data: field tambahan bebas, mis. payload=..., output=..., error=...
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step_name": step_name,
        "status": status,
        **{key: _json_safe(val) for key, val in data.items()},
    }
    print(json.dumps(log_entry, indent=2, ensure_ascii=False, default=str))


def _log_error(step_name: str, error: Exception, **extra: Any) -> None:
    """Helper khusus untuk mencetak log JSON saat terjadi exception."""
    _log_json(
        step_name,
        "ERROR",
        error_type=type(error).__name__,
        error_message=str(error),
        traceback=traceback.format_exc(),
        **extra,
    )


# --------------------------------------------------------------------------
# Helper umum
# --------------------------------------------------------------------------

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


def _build_placeholder_asset(asset_id: str) -> dict[str, Any]:
    """
    Membuat entri asset placeholder untuk asset_id yang direferensikan oleh
    process_stages tapi tidak ada di daftar assets hasil ekstraksi LLM
    (kemungkinan LLM 'berhalusinasi' referensi asset yang tidak ia definisikan
    sendiri). Semua field wajib diisi agar tetap lolos validasi skema
    `dt_schemas.Asset` (mis. `raw` pada Quantity tidak boleh null) sekaligus
    aman disimpan ke database (memenuhi FK `process_stages.asset_id`).

    Pendekatan ini dipilih ketimbang meng-null-kan `asset_id` pada stage,
    karena skema `ProcessStage.asset_id` mewajibkan string non-kosong
    (`minLength: 1`) -- meng-null-kan field ini akan gagal validasi Pydantic
    sebelum data sempat disimpan sama sekali.
    """
    return {
        "asset_id": asset_id,
        "asset_name": f"Asset Tidak Dikenal ({asset_id})",
        "category": "manual_station",
        "units_available": 1,
        "capacity_per_unit": {
            "raw": "Tidak diketahui (asset placeholder otomatis)",
            "value": None,
            "unit": None,
            "unit_class": None,
            "basis": None,
        },
        "total_capacity": {
            "raw": "Tidak diketahui (asset placeholder otomatis)",
            "value": None,
            "unit": None,
            "unit_class": None,
            "basis": None,
        },
        "automation_level": "manual",
        "is_automated": False,
        "operational_cost_per_hour": 0,
        "currency": "IDR",
        "environmental_factors": {
            "power_consumption_watt": None,
            "noise_level_db": None,
            "vibration_hazard_level": "low",
            "physical_strain_index": 0,
        },
        "metric_derivation_reasoning": (
            f"Asset placeholder dibuat otomatis karena asset_id '{asset_id}' "
            f"direferensikan oleh process stage namun tidak terdaftar pada "
            f"daftar assets hasil ekstraksi dokumen. Data metrik aktual perlu "
            f"diverifikasi/dilengkapi secara manual."
        ),
    }


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
    meratakan (flatten) nested compatibility_matrix, serta memvalidasi:
    - setiap worker_id pada evaluasi terdaftar di daftar workers
    - setiap asset_id yang direferensikan process_stages terdaftar di daftar assets
    untuk mencegah ForeignKeyViolationError di PostgreSQL.
    """
    _log_json("build_digital_twin_from_results", "START")

    if warnings is None:
        warnings = []

    try:
        fac_dict = _to_dict(factory_structure)
        wrk_dict = _to_dict(worker_profile)
        mat_dict = (
            _to_dict(compatibility_matrix)
            if not isinstance(compatibility_matrix, list)
            else {"llm_compatibility_and_evaluations": compatibility_matrix}
        )

        # 1. Ekstraksi Factory Info, Assets, Process Stages & Shifts
        factory_info_data = fac_dict.get("factory_info", {})
        assets_data = fac_dict.get("assets", [])
        process_stages_data = fac_dict.get("process_stages", [])
        shifts_data = fac_dict.get("shifts", [])

        _log_json(
            "build_digital_twin_from_results.extract_factory",
            "SUCCESS",
            factory_id=factory_info_data.get("factory_id"),
            assets_count=len(assets_data) if isinstance(assets_data, list) else 0,
            process_stages_count=len(process_stages_data) if isinstance(process_stages_data, list) else 0,
            shifts_count=len(shifts_data) if isinstance(shifts_data, list) else 0,
        )

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

        # Kumpulkan seluruh asset_id yang valid (untuk validasi referensi process_stages)
        valid_asset_ids: set[str] = set()
        if isinstance(assets_data, list):
            for a in assets_data:
                a_item = _to_dict(a)
                a_id = a_item.get("asset_id")
                if a_id:
                    valid_asset_ids.add(str(a_id))

        # Validasi process_stages: asset_id wajib terdaftar di daftar assets,
        # agar tidak memicu ForeignKeyViolationError saat insert ke tabel process_stages.
        #
        # PENTING: asset_id TIDAK di-null-kan bila tidak ditemukan (percobaan sebelumnya
        # melakukan ini, tapi skema ProcessStage.asset_id mewajibkan string non-kosong
        # sehingga null akan gagal validasi Pydantic). Sebagai gantinya, dibuatkan
        # asset placeholder otomatis (lihat `_build_placeholder_asset`) agar referensi
        # tetap valid baik di level skema Pydantic maupun FK database.
        placeholder_asset_ids_created: set[str] = set()
        filtered_stages: list[dict[str, Any]] = []
        if isinstance(process_stages_data, list):
            for stage in process_stages_data:
                stage_dict = _to_dict(stage)
                stage_asset_id = str(stage_dict.get("asset_id") or "")
                if stage_asset_id and stage_asset_id not in valid_asset_ids:
                    if stage_asset_id not in placeholder_asset_ids_created:
                        assets_data = list(assets_data) + [_build_placeholder_asset(stage_asset_id)]
                        valid_asset_ids.add(stage_asset_id)
                        placeholder_asset_ids_created.add(stage_asset_id)
                    warnings.append(
                        f"Process stage '{stage_dict.get('stage_id')}' mereferensikan "
                        f"asset_id '{stage_asset_id}' yang tidak terdaftar pada daftar assets; "
                        f"asset placeholder otomatis telah dibuat agar integritas referensial "
                        f"tetap terjaga. Data metrik asset ini perlu diverifikasi manual."
                    )
                filtered_stages.append(stage_dict)
        process_stages_data = filtered_stages

        _log_json(
            "build_digital_twin_from_results.validate_workers_assets",
            "SUCCESS",
            valid_worker_ids_count=len(valid_worker_ids),
            valid_asset_ids_count=len(valid_asset_ids),
            placeholder_assets_created=len(placeholder_asset_ids_created),
            job_desks_count=len(job_desks_data) if isinstance(job_desks_data, list) else 0,
        )

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

        _log_json(
            "build_digital_twin_from_results.flatten_compatibility_matrix",
            "SUCCESS",
            evaluated_pairs=len(filtered_evals),
            warnings_count=len(warnings),
        )

        dt_payload = {
            "factory_info": factory_info_data,
            "assets": assets_data,
            "process_stages": process_stages_data,
            "shifts": shifts_data,
            "job_desks": job_desks_data,
            "workers": workers_data,
            "llm_compatibility_and_evaluations": filtered_evals,
            "warnings": warnings,
        }

        dt_model = dt_schemas.DigitalTwin.model_validate(dt_payload)

        _log_json(
            "build_digital_twin_from_results",
            "SUCCESS",
            factory_id=factory_info_data.get("factory_id"),
            assets_count=len(assets_data),
            process_stages_count=len(process_stages_data),
            workers_count=len(workers_data) if isinstance(workers_data, list) else 0,
            job_desks_count=len(job_desks_data) if isinstance(job_desks_data, list) else 0,
            warnings_count=len(warnings),
        )

        return dt_model

    except Exception as error:
        _log_error("build_digital_twin_from_results", error)
        raise


# --------------------------------------------------------------------------
# Tahap 1 & 2 Terpadu: Ekstraksi Dokumen & Generasi Struktur Pabrik
# --------------------------------------------------------------------------

async def process_factory_document_pipeline(
    template: UploadFile,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Menggabungkan Tahap 1 (Ekstraksi Dokumen Pabrik) dan Tahap 2 (Agent A)
    menjadi satu kesatuan alur proses.
    """
    filename = template.filename or "template.pdf"
    _log_json("process_factory_document_pipeline", "START", payload={"filename": filename})

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
        _log_json(
            "process_factory_document_pipeline.audit_job_created",
            "SUCCESS",
            output={"job_id": job.id, "status": job.status},
        )

    warnings: list[str] = []

    try:
        # 1. Ekstraksi File Dokumen
        with tempfile.TemporaryDirectory(prefix="doc_pipeline_") as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(await template.read())

            try:
                # `source` bisa berupa objek PDF/DOCX (Document) atau mode Workbook
                source = await run_in_threadpool(extract_any, tmp_path)
            except (UnsupportedDocumentError, UnsupportedWorkbookError) as error:
                raise DocumentParserPipelineError("extract", str(error)) from error

        # Mengambil atribut secara defensif karena mode workbook mungkin tidak memilikinya
        tables = getattr(source, "tables", [])
        tables_count = len(tables)
        text_fields = getattr(source, "text_fields", {})
        raw_text = getattr(source, "raw_text", "")

        _log_json(
            "process_factory_document_pipeline.extract_document",
            "SUCCESS",
            output={
                "tables_count": tables_count,
                "text_fields_count": len(text_fields),
            },
        )

        # Validasi kelengkapan dokumen mentah
        if tables_count < 3:
            warnings.append(
                f"Dokumen template hanya berisi {tables_count} tabel (diharapkan 3)."
            )

        missing_tables_func = getattr(source, "missing_tables", None)
        if callable(missing_tables_func):
            missing_tables = missing_tables_func()
            if missing_tables:
                warnings.append(
                    f"Tabel yang tidak terdeteksi: {', '.join(f'Tabel {t}' for t in missing_tables)}"
                )

        missing_fields_func = getattr(source, "missing_text_fields", None)
        if callable(missing_fields_func):
            missing_fields = missing_fields_func()
            if missing_fields:
                warnings.append(f"Field template belum terbaca: {', '.join(missing_fields)}")

        if warnings:
            _log_json(
                "process_factory_document_pipeline.validate_document",
                "SUCCESS",
                payload={"warnings": warnings},
            )

        # 2. Formulasi prompt untuk Agent A
        agent_input = build_any_agent_input(source)

        # 3. Eksekusi Agent A (Struktur Pabrik)
        registry = get_agent_registry()
        factory_agent = registry.get(AgentRole.FACTORY_STRUCTURE)

        _log_json("process_factory_document_pipeline.agent_factory_structure", "START")
        try:
            twin = await run_in_threadpool(
                factory_agent.generate_structured, user_prompt=agent_input
            )
        except Exception as error:
            raise DocumentParserPipelineError(
                "llm_parse", f"Agent struktur pabrik gagal: {error}"
            ) from error

        fac_structure_dict = _to_dict(twin)
        _log_json(
            "process_factory_document_pipeline.agent_factory_structure",
            "SUCCESS",
            output={
                "factory_id": fac_structure_dict.get("factory_info", {}).get("factory_id"),
                "assets_count": len(fac_structure_dict.get("assets", [])),
                "process_stages_count": len(fac_structure_dict.get("process_stages", [])),
            },
        )

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
            _log_json(
                "process_factory_document_pipeline.audit_job_updated",
                "SUCCESS",
                output={"job_id": job.id, "status": job.status},
            )

        # Menggunakan field yang sudah diekstrak secara defensif
        result = {
            "parse_job_id": job.id if job else None,
            "extraction_summary": {
                "extracted_fields": text_fields,
                "tables_count": tables_count,
                "raw_text": raw_text,
                "warnings": warnings,
            },
            "agent_input": agent_input,
            "factory_structure": twin,
        }

        _log_json(
            "process_factory_document_pipeline",
            "SUCCESS",
            output={"parse_job_id": result["parse_job_id"], "warnings_count": len(warnings)},
        )

        return result

    except DocumentParserPipelineError as err:
        _log_error("process_factory_document_pipeline", err, payload={"stage": err.stage})
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = err.stage
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception as inner_err:
                _log_error("process_factory_document_pipeline.audit_job_error_write", inner_err)
        raise err
    except Exception as err:
        _log_error("process_factory_document_pipeline", err)
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = "unknown"
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception as inner_err:
                _log_error("process_factory_document_pipeline.audit_job_error_write", inner_err)
        raise err


# --------------------------------------------------------------------------
# Tahap 4: Ekstraksi ZIP CV & Agent B (Profil Pekerja)
# --------------------------------------------------------------------------

WORKER_PROFILE_CHUNK_SIZE = 4  # jumlah CV per panggilan LLM, tuning berdasarkan max_tokens agent


async def step_4_extract_worker_profiles(
    worker_zip: UploadFile,
    strict: bool = False,
    max_workers: int = 4,
    max_attempts: int = 3,
) -> dict[str, Any]:
    filename = worker_zip.filename or "workers.zip"
    _log_json(
        "step_4_extract_worker_profiles",
        "START",
        payload={
            "filename": filename,
            "strict": strict,
            "max_workers": max_workers,
            "max_attempts": max_attempts,
        },
    )

    _validate_suffix(filename, WORKER_SUFFIXES, "worker_zip")

    try:
        with tempfile.TemporaryDirectory(prefix="worker_step4_") as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(await worker_zip.read())

            try:
                worker_document, archive_reports = await run_in_threadpool(
                    extract_worker_uploads, [tmp_path], strict=strict,
                )
            except (ArchiveError, UnsupportedDocumentError) as error:
                raise DocumentParserPipelineError("extract", str(error)) from error
            except Exception as error:
                raise DocumentParserPipelineError(
                    "extract", f"Gagal mengekstraksi arsip ZIP pekerja: {error}"
                ) from error

            worker_agent_input = build_worker_agent_input(worker_document)

        _log_json(
            "step_4_extract_worker_profiles.extract_archive",
            "SUCCESS",
            output={
                "candidates_found": len(worker_document.candidates),
                "rejected_blocks_count": len(worker_document.rejected_blocks),
                "archives_count": len(archive_reports),
            },
        )

        registry = get_agent_registry()
        worker_agent = registry.get(AgentRole.WORKER_PROFILE)

        _log_json("step_4_extract_worker_profiles.agent_worker_profile", "START")
        try:
            result = await run_in_threadpool(
                generate_worker_profiles,
                document=worker_document,
                agent=worker_agent,
                candidate_payload=candidate_payload,
                max_workers=max_workers,
                max_attempts=max_attempts,
                strict=strict,
            )
        except WorkerProfileGenerationError as error:
            raise DocumentParserPipelineError(
                "llm_parse", f"Agent profil pekerja gagal: {error}"
            ) from error

        result_dict = _to_dict(result)
        _log_json(
            "step_4_extract_worker_profiles.agent_worker_profile",
            "SUCCESS",
            output={"workers_count": len(result_dict.get("workers", []))},
        )

        payload = {
            "worker_profile": result,
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

        _log_json(
            "step_4_extract_worker_profiles",
            "SUCCESS",
            output={
                "candidates_found": payload["candidates_found"],
                "rejected_blocks_count": payload["rejected_blocks_count"],
            },
        )

        return payload

    except DocumentParserPipelineError as err:
        _log_error("step_4_extract_worker_profiles", err, payload={"stage": err.stage})
        raise
    except Exception as err:
        _log_error("step_4_extract_worker_profiles", err)
        raise


# --------------------------------------------------------------------------
# Tahap 5: Matriks Kompatibilitas
# --------------------------------------------------------------------------

async def step_5_generate_compatibility_matrix(
    factory_structure: dict[str, Any],
    worker_profile: dict[str, Any],
    max_workers: int = 4,
    max_attempts: int = 3,
    strict_compatibility: bool = False,
) -> dict[str, Any]:
    """Memetakan pencocokan job desk pabrik dengan profil pekerja."""
    _log_json(
        "step_5_generate_compatibility_matrix",
        "START",
        payload={
            "max_workers": max_workers,
            "max_attempts": max_attempts,
            "strict_compatibility": strict_compatibility,
        },
    )

    try:
        worker_list = (
            worker_profile.get("workers", [])
            if isinstance(worker_profile, dict)
            else getattr(worker_profile, "workers", [])
        )

        registry = get_agent_registry()
        compatibility_agent = registry.get(AgentRole.WORKER_COMPATIBILITY)

        _log_json(
            "step_5_generate_compatibility_matrix.agent_compatibility",
            "START",
            payload={"worker_count": len(worker_list) if isinstance(worker_list, list) else 0},
        )
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

        _log_json("step_5_generate_compatibility_matrix.agent_compatibility", "SUCCESS")

        result = {
            "compatibility_matrix": matrix,
            "warnings": [],
        }

        _log_json("step_5_generate_compatibility_matrix", "SUCCESS")

        return result

    except DocumentParserPipelineError as err:
        _log_error("step_5_generate_compatibility_matrix", err, payload={"stage": err.stage})
        raise
    except Exception as err:
        _log_error("step_5_generate_compatibility_matrix", err)
        raise


# --------------------------------------------------------------------------
# Fungsi Kombinasi: Tahap 1+2, Tahap 4, & Tahap 5 (Persisted & Ingested)
# --------------------------------------------------------------------------

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

    CATATAN FIX: `job.factory_id` (serta `job_desks_parsed` & `workers_parsed`) HANYA
    diisi bila ingestion ke Digital Twin DB benar-benar berhasil. Sebelumnya field ini
    selalu diisi walau savepoint ingestion di-rollback akibat error (mis. FK violation
    pada `process_stages.asset_id`), sehingga `document_parse_jobs.factory_id` menunjuk
    ke row `factories` yang tidak pernah tersimpan -> memicu ForeignKeyViolationError
    kedua saat `db.commit()` dan berakhir sebagai 500 Internal Server Error.
    """
    template_filename = template.filename or "template.pdf"
    cv_bundle_filename = worker_zip.filename or "workers.zip"

    _log_json(
        "process_combined_documents_pipeline",
        "START",
        payload={
            "template_filename": template_filename,
            "cv_bundle_filename": cv_bundle_filename,
            "strict": strict,
            "max_workers": max_workers,
            "max_attempts": max_attempts,
        },
    )

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
        _log_json(
            "process_combined_documents_pipeline.audit_job_created",
            "SUCCESS",
            output={"job_id": job.id, "status": job.status},
        )

    try:
        # 1. Jalankan Tahap 1 & 2 (Pabrik)
        factory_result = await process_factory_document_pipeline(template)

        # 2. Jalankan Tahap 4 (Pekerja)
        worker_result = await step_4_extract_worker_profiles(
            worker_zip, strict=strict, max_workers=max_workers, max_attempts=max_attempts
        )

        # 3. Jalankan Tahap 5 (Matriks Kompatibilitas)
        compatibility_result = await step_5_generate_compatibility_matrix(
            factory_structure=factory_result["factory_structure"],
            worker_profile=worker_result["worker_profile"],
            max_workers=max_workers,
            max_attempts=max_attempts,
            strict_compatibility=strict,
        )

        response_payload = {
            # Di-cast ke str secara eksplisit: kolom `DocumentParseJob.id` bertipe
            # Integer di database, sementara skema response `ProcessCombinedDocumentsResponse
            # .parse_job_id` mendeklarasikan tipe `str | None`. Tanpa cast ini, Pydantic
            # akan menolak int di endpoint dengan pydantic_core.ValidationError
            # (`Input should be a valid string [type=string_type, input_value=4, ...]`).
            "parse_job_id": str(job.id) if job else None,
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

        _log_json(
            "process_combined_documents_pipeline.all_stages_completed",
            "SUCCESS",
            output={
                "parse_job_id": response_payload["parse_job_id"],
                "candidates_found": response_payload["candidates_found"],
            },
        )

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
            ingestion_succeeded = False

            _log_json(
                "process_combined_documents_pipeline.ingest_digital_twin",
                "START",
                payload={"factory_id": dt_model.factory_info.factory_id},
            )
            try:
                # Gunakan savepoint transaksi terisolasi agar kegagalan DB tidak merusak session
                async with db.begin_nested():
                    await dt_service.save_digital_twin(dt_model)
                ingestion_succeeded = True
                _log_json(
                    "process_combined_documents_pipeline.ingest_digital_twin",
                    "SUCCESS",
                    output={"factory_id": dt_model.factory_info.factory_id},
                )
            except Exception as dt_err:
                # Savepoint sudah di-rollback otomatis oleh `db.begin_nested()` context manager;
                # row Factory/Asset/dll yang sempat ditambahkan di dalam blok ini TIDAK tersimpan.
                warnings.append(f"Gagal melakukan ingestion ke Digital Twin DB: {dt_err}")
                _log_error(
                    "process_combined_documents_pipeline.ingest_digital_twin",
                    dt_err,
                    payload={"factory_id": dt_model.factory_info.factory_id},
                )

            # Update audit trail record dengan hasil normalisasi.
            # PENTING: factory_id/job_desks_parsed/workers_parsed HANYA diisi bila
            # ingestion sukses, agar tidak menunjuk ke row `factories` yang tidak ada
            # (mencegah ForeignKeyViolationError kedua saat commit di bawah).
            job.status = "success" if ingestion_succeeded else "partial_success"
            job.factory_id = dt_model.factory_info.factory_id if ingestion_succeeded else None
            job.job_desks_parsed = len(dt_model.job_desks) if ingestion_succeeded else 0
            job.workers_parsed = len(dt_model.workers) if ingestion_succeeded else 0
            job.warnings = warnings
            job.factory_structure = _to_dict(factory_result["factory_structure"])
            job.worker_profile = _to_dict(worker_result["worker_profile"])
            job.compatibility_matrix = _to_dict(compatibility_result["compatibility_matrix"])

            await db.commit()
            await db.refresh(job)

            _log_json(
                "process_combined_documents_pipeline.audit_job_updated",
                "SUCCESS",
                output={
                    "job_id": job.id,
                    "status": job.status,
                    "factory_id": job.factory_id,
                    "ingestion_succeeded": ingestion_succeeded,
                    "warnings_count": len(warnings),
                },
            )

        _log_json(
            "process_combined_documents_pipeline",
            "SUCCESS",
            output={"parse_job_id": response_payload["parse_job_id"]},
        )

        return response_payload

    except DocumentParserPipelineError as err:
        _log_error("process_combined_documents_pipeline", err, payload={"stage": err.stage})
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = err.stage
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception as inner_err:
                _log_error("process_combined_documents_pipeline.audit_job_error_write", inner_err)
        raise err
    except Exception as err:
        _log_error("process_combined_documents_pipeline", err)
        if db is not None and job is not None:
            try:
                await db.rollback()
                job.status = "error"
                job.error_stage = "unknown"
                job.error_message = str(err)
                db.add(job)
                await db.commit()
            except Exception as inner_err:
                _log_error("process_combined_documents_pipeline.audit_job_error_write", inner_err)
        raise err


async def get_parsed_factories_list(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Mengambil daftar pekerjaan parsing pabrik yang berhasil tersimpan di database.
    """
    _log_json("get_parsed_factories_list", "START", payload={"limit": limit, "offset": offset})

    try:
        query = (
            select(DocumentParseJob)
            .where(DocumentParseJob.status == "success")
            .order_by(DocumentParseJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(query)
        jobs = result.scalars().all()

        factory_list: list[dict[str, Any]] = []
        for job in jobs:
            fac_structure = job.factory_structure or {}
            factory_info = fac_structure.get("factory_info", {})

            factory_id = job.factory_id or factory_info.get("factory_id") or job.id
            factory_name = (
                factory_info.get("factory_name")
                or fac_structure.get("factory_name")
                or f"Factory {factory_id[:8]}"
            )

            factory_list.append({
                "factory_id": factory_id,
                "factory_name": factory_name,
                "workers_count": job.workers_parsed or 0,
                "job_desks_count": job.job_desks_parsed or 0,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            })

        _log_json(
            "get_parsed_factories_list",
            "SUCCESS",
            output={"factories_count": len(factory_list)},
        )

        return factory_list

    except Exception as error:
        _log_error("get_parsed_factories_list", error)
        raise