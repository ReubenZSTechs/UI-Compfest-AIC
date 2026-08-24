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
5. FIX RUNTIME BUG: Penggunaan `str(factory_id)[:8]` pada `get_parsed_factories_list` untuk
   mencegah TypeError jika `factory_id` bernilai `int`.
6. UPDATE FACTORY ID LOGIC: Memperbarui fungsi untuk menggunakan ID kanonik sehingga sinkron 
   antara API response dan baris database. Mengatasi 404 GET /digitaltwin/{id}.
7. BARU: `process_combined_documents_manual_pipeline` -- versi Kombinasi Tahap 1, 2, 4, & 5
   yang menerima data langsung dari form frontend (bukan PDF/ZIP), dengan validasi silang
   FK (setara node D01-D08 pada spesifikasi flowchart form manual) dilakukan SEBELUM data
   coba disimpan ke DB, sehingga kesalahan seperti `stage_id` kosong terdeteksi lebih awal
   dan dengan pesan yang jelas, bukan sebagai `IntegrityError` dari Postgres.
"""

from __future__ import annotations

import json
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.modules.digital_twin_ingestion import schemas as dt_schemas
from app.modules.digital_twin_ingestion.models import Factory
from app.modules.documents import schemas
from app.modules.documents.models import DocumentParseJob

from app.services.agent_registry_service import AgentRole, get_agent_registry
from app.services.cross_reference_job_worker_service import (
    CompatibilityEvaluationError,
    generate_compatibility_matrix,
)
from app.services.cv_pdf_parser_service import (
    build_worker_agent_input,
    candidate_payload,
)
from app.services.extract_input_field_service import (
    UnsupportedDocumentError,
    build_agent_input,
    extract_any,
)
from app.services.extract_worker_archive_service import (
    ArchiveError,
    extract_worker_uploads,
)
from app.services.generate_worker_profiles_service import (
    WorkerProfileGenerationError,
    generate_worker_profiles,
)

from .exceptions import DocumentParserPipelineError

from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.modules.documents.repository import (
    _flatten_compatibility_matrix,
    _unwrap_worker_profile,
    persist_compatibility_matrix,
    persist_completed_pipeline,
    persist_worker_profile,
    record_failed_parse_job,
)

# Dukungan ekstensi file template & CV pekerja
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
# Helper Umum
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


def assign_canonical_factory_id(
    factory_structure: dict[str, Any],
    factory_id: str | None = None,
) -> str:
    """
    Menetapkan `factory_info.factory_id` ke bentuk kanonik SATU KALI, sebelum data
    dipersist -- menggantikan `_apply_job_id_to_factory_id()` yang dulu menempelkan
    sufiks `-job{N}` SETELAH `persist_completed_pipeline()` selesai. Pola lama itu
    membuat id yang dikembalikan API tidak pernah cocok dengan baris yang benar-benar
    tersimpan, sehingga `GET /digitaltwin/{id}` selalu 404 untuk hasil alur otomatis.
    Format kanoniknya sama persis dengan alur manual (`POST /factories`), yaitu
    `DigitalTwinService.generate_factory_id()` -- satu konvensi id untuk kedua alur.
    Id hasil ekstraksi LLM tidak dipakai sebagai primary key karena tidak dijamin
    unik antar-dokumen.
    """
    factory_info = factory_structure.get("factory_info")
    if not isinstance(factory_info, dict):
        factory_info = {}
        factory_structure["factory_info"] = factory_info
    resolved = (factory_id or "").strip() or DigitalTwinService.generate_factory_id()
    factory_info["factory_id"] = resolved
    return resolved


def _build_placeholder_asset(asset_id: str) -> dict[str, Any]:
    """
    Membuat entri asset placeholder untuk asset_id yang direferensikan oleh
    process_stages tapi tidak ada di daftar assets hasil ekstraksi LLM.
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
            f"direferensikan oleh process stage namun tidak terdaftar pada assets."
        ),
    }


def build_digital_twin_from_results(
    factory_structure: Any,
    worker_profile: Any,
    compatibility_matrix: Any,
    warnings: list[str] | None = None,
) -> dt_schemas.DigitalTwin:
    """
    Helper untuk mengonversi hasil parsing mentah menjadi skema DigitalTwin Pydantic yang valid.
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

        factory_info_data = fac_dict.get("factory_info", {})
        assets_data = fac_dict.get("assets", [])
        process_stages_data = fac_dict.get("process_stages", [])
        shifts_data = fac_dict.get("shifts", [])
        job_desks_data = fac_dict.get("job_desks") or fac_dict.get("job_descriptions") or []

        workers_data = wrk_dict.get("workers", wrk_dict if isinstance(wrk_dict, list) else [])
        if isinstance(workers_data, dict) and "workers" in workers_data:
            workers_data = workers_data["workers"]

        valid_worker_ids: set[str] = set()
        if isinstance(workers_data, list):
            for w in workers_data:
                w_item = _to_dict(w)
                w_id = w_item.get("worker_id") or w_item.get("id") or w_item.get("worker_code")
                if w_id:
                    valid_worker_ids.add(str(w_id))

        valid_asset_ids: set[str] = set()
        if isinstance(assets_data, list):
            for a in assets_data:
                a_item = _to_dict(a)
                a_id = a_item.get("asset_id")
                if a_id:
                    valid_asset_ids.add(str(a_id))

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
                        f"Process stage '{stage_dict.get('stage_id')}' mereferensikan asset_id '{stage_asset_id}' "
                        f"yang tidak terdaftar pada assets; asset placeholder dibuat otomatis."
                    )
                filtered_stages.append(stage_dict)
        process_stages_data = filtered_stages

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
    factory_id: str | None = None,
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
        job = DocumentParseJob(status="in_progress", template_filename=filename)
        db.add(job)
        await db.commit()
        await db.refresh(job)

    warnings: list[str] = []

    try:
        with tempfile.TemporaryDirectory(prefix="doc_pipeline_") as tmp_dir:
            tmp_path = Path(tmp_dir) / filename
            tmp_path.write_bytes(await template.read())

            try:
                source = await run_in_threadpool(extract_any, tmp_path)
            except UnsupportedDocumentError as error:
                raise DocumentParserPipelineError("extract", str(error)) from error

        tables = getattr(source, "tables", [])
        tables_count = len(tables)
        text_fields = getattr(source, "text_fields", {})
        raw_text = getattr(source, "raw_text", "")

        if tables_count < 3:
            warnings.append(f"Dokumen template hanya berisi {tables_count} tabel (diharapkan 3).")

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

        agent_input = build_agent_input(source)

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
        extracted_id = (fac_structure_dict.get("factory_info") or {}).get("factory_id")
        resolved_factory_id = assign_canonical_factory_id(fac_structure_dict, factory_id)
        
        if extracted_id and extracted_id != resolved_factory_id:
            warnings.append(
                f"factory_id hasil ekstraksi ('{extracted_id}') diganti dengan id "
                f"kanonik '{resolved_factory_id}' agar konsisten dengan alur manual."
            )

        if db is not None and job is not None:
            parsed_job_desks = (
                fac_structure_dict.get("job_desks")
                or fac_structure_dict.get("job_descriptions")
                or []
            )
            job.status = "success"
            # FK document_parse_jobs.factory_id -> factories.factory_id: tahap ini
            # belum menulis baris `factories` apa pun (persistence penuh baru terjadi
            # di persist_completed_pipeline), jadi id hanya ditautkan bila barisnya
            # memang sudah ada. Tanpa guard ini commit di bawah kena IntegrityError.
            job.factory_id = (
                resolved_factory_id
                if await db.get(Factory, resolved_factory_id) is not None
                else None
            )
            job.job_desks_parsed = len(parsed_job_desks)
            job.warnings = warnings
            job.factory_structure = fac_structure_dict
            await db.commit()
            await db.refresh(job)

        return {
            "parse_job_id": str(job.id) if (job and job.id) else None,
            "extraction_summary": {
                "extracted_fields": text_fields,
                "tables_count": tables_count,
                "raw_text": raw_text,
                "warnings": warnings,
            },
            "agent_input": agent_input,
            "factory_structure": fac_structure_dict,
        }

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

DEMOGRAPHIC_DEFAULTS: dict[str, Any] = {
    "age": 30,
    "gender": "unknown",
    "years_of_experience": 0.0,
    "baseline_physical_stamina": 0.5,
    "cognitive_resilience": 0.5,
}

SHIFT_CONTEXT_DEFAULTS: dict[str, Any] = {
    "hours_worked_today": 0.0,
    "consecutive_shifts": 0,
}


def _normalize_worker_records(worker_profile: Any) -> tuple[dict[str, Any], list[str]]:
    """
    Melengkapi hasil ekstraksi ZIP yang tidak utuh sebelum masuk ke DB: worker_id
    kosong diberi ID otomatis, worker_id duplikat di-suffix, dan field demografi /
    shift_context yang hilang diisi nilai default. Tanpa langkah ini, baris worker
    yang tidak lengkap akan lolos ke tabel `workers` dan baru meledak saat dibaca
    kembali sebagai skema Pydantic pada endpoint retrieval.
    """
    profile = _unwrap_worker_profile(worker_profile)
    warnings: list[str] = []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, raw in enumerate(profile.get("workers", []), start=1):
        if not isinstance(raw, dict):
            warnings.append(f"Entri pekerja ke-{index} diabaikan karena bukan objek JSON.")
            continue

        record = dict(raw)
        worker_id = str(
            record.get("worker_id") or record.get("id") or record.get("worker_code") or ""
        ).strip()

        if not worker_id:
            worker_id = f"wrk-auto-{index:03d}"
            warnings.append(
                f"Pekerja ke-{index} tidak memiliki worker_id; ID '{worker_id}' dibuat otomatis."
            )

        if worker_id in seen:
            duplicated = worker_id
            worker_id = f"{worker_id}-{index:03d}"
            warnings.append(
                f"worker_id '{duplicated}' duplikat di dalam arsip; diubah menjadi '{worker_id}'."
            )

        seen.add(worker_id)

        demographics = record.get("demographics")
        demographics = demographics if isinstance(demographics, dict) else {}
        missing_demo = [
            key for key in DEMOGRAPHIC_DEFAULTS if demographics.get(key) is None
        ]
        if missing_demo:
            warnings.append(
                f"Pekerja '{worker_id}' tidak memiliki demografi lengkap "
                f"({', '.join(missing_demo)}); nilai default dipakai."
            )

        shift_context = record.get("shift_context")
        shift_context = shift_context if isinstance(shift_context, dict) else {}
        missing_shift = [
            key for key in SHIFT_CONTEXT_DEFAULTS if shift_context.get(key) is None
        ]
        if missing_shift:
            warnings.append(
                f"Pekerja '{worker_id}' tidak memiliki shift_context lengkap "
                f"({', '.join(missing_shift)}); nilai default dipakai."
            )

        record["worker_id"] = worker_id
        record["name"] = str(record.get("name") or worker_id)
        record["demographics"] = {
            **DEMOGRAPHIC_DEFAULTS,
            **{k: v for k, v in demographics.items() if v is not None},
        }
        record["shift_context"] = {
            **SHIFT_CONTEXT_DEFAULTS,
            **{k: v for k, v in shift_context.items() if v is not None},
        }
        normalized.append(record)

    if not normalized:
        warnings.append("Tidak ada profil pekerja valid yang berhasil diekstraksi dari arsip.")

    return {"workers": normalized}, warnings


async def _persist_workers_to_factory(
    db: AsyncSession, factory_id: str, worker_profile: dict[str, Any]
) -> int:
    """Menyimpan hasil Tahap 4 ke tabel `workers` dengan FK ke factory_id."""
    factory = await db.get(Factory, factory_id)
    if factory is None:
        raise DocumentParserPipelineError(
            "factory_lookup",
            f"Factory '{factory_id}' tidak ditemukan. Buat factory terlebih dahulu "
            f"melalui POST /factories sebelum mengunggah ZIP CV.",
        )

    try:
        persisted = await persist_worker_profile(db, factory_id, worker_profile)
        factory.registered_worker_count = persisted
        await db.commit()
    except Exception as error:
        await db.rollback()
        raise DocumentParserPipelineError(
            "ingestion", f"Gagal menyimpan profil pekerja ke database: {error}"
        ) from error

    return persisted


async def step_4_extract_worker_profiles(
    worker_zip: UploadFile,
    strict: bool = False,
    max_workers: int = 4,
    max_attempts: int = 3,
    factory_id: str | None = None,
    db: AsyncSession | None = None,
) -> dict[str, Any]:
    """Ekstraksi berkas arsip CV pekerja dan pembuatan profil terstruktur."""
    filename = worker_zip.filename or "workers.zip"
    _log_json(
        "step_4_extract_worker_profiles",
        "START",
        payload={
            "filename": filename,
            "factory_id": factory_id,
            "strict": strict,
            "max_workers": max_workers,
            "max_attempts": max_attempts,
        },
    )

    _validate_suffix(filename, WORKER_SUFFIXES, "worker_zip")

    try:
        if factory_id and db is not None:
            if await db.get(Factory, factory_id) is None:
                raise DocumentParserPipelineError(
                    "factory_lookup",
                    f"Factory '{factory_id}' tidak ditemukan. Buat factory terlebih "
                    f"dahulu melalui POST /factories.",
                )

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

        if not worker_document.candidates:
            raise DocumentParserPipelineError(
                "extract",
                "Arsip ZIP tidak memuat satu pun dokumen CV yang bisa dibaca "
                "(.pdf, .docx, .md, .txt).",
            )

        registry = get_agent_registry()
        worker_agent = registry.get(AgentRole.WORKER_PROFILE)

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

        worker_profile, warnings = _normalize_worker_records(_to_dict(result))

        workers_persisted = 0
        if factory_id and db is not None:
            if not worker_profile["workers"]:
                raise DocumentParserPipelineError(
                    "ingestion",
                    "Tidak ada profil pekerja valid untuk disimpan; periksa isi arsip ZIP.",
                    details=warnings,
                )
            workers_persisted = await _persist_workers_to_factory(
                db, factory_id, worker_profile
            )

        return {
            "factory_id": factory_id,
            "worker_profile": worker_profile,
            "worker_agent_input": worker_agent_input,
            "candidates_found": len(worker_document.candidates),
            "rejected_blocks_count": len(worker_document.rejected_blocks),
            "workers_persisted": workers_persisted,
            "archive_reports": [
                {
                    "archive_name": r.archive_name,
                    "accepted_count": r.accepted_count(),
                    "skipped": r.skipped,
                    "failed": r.failed,
                }
                for r in archive_reports
            ],
            "warnings": warnings,
        }

    except DocumentParserPipelineError as err:
        _log_error("step_4_extract_worker_profiles", err, payload={"stage": err.stage})
        raise
    except Exception as err:
        _log_error("step_4_extract_worker_profiles", err)
        raise


# --------------------------------------------------------------------------
# Tahap 5: Matriks Kompatibilitas
# --------------------------------------------------------------------------


def _read_worker_list(worker_profile: Any) -> list[dict[str, Any]]:
    profile = _unwrap_worker_profile(worker_profile)
    return [w for w in profile.get("workers", []) if isinstance(w, dict)]


async def step_5_generate_compatibility_matrix(
    factory_structure: dict[str, Any] | None = None,
    worker_profile: dict[str, Any] | None = None,
    max_workers: int = 4,
    max_attempts: int = 3,
    strict_compatibility: bool = False,
    factory_id: str | None = None,
    db: AsyncSession | None = None,
    persist: bool = True,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Memetakan pencocokan job desk pabrik dengan profil pekerja.

    Bila `factory_id` diberikan, struktur pabrik & daftar pekerja dibaca langsung
    dari Digital Twin DB (hasil Tahap 4 + flowchart manual), dan matriks hasilnya
    dipersist balik ke tabel `compatibility_evaluations` milik factory tersebut.
    """
    _log_json(
        "step_5_generate_compatibility_matrix",
        "START",
        payload={
            "factory_id": factory_id,
            "max_workers": max_workers,
            "max_attempts": max_attempts,
            "strict_compatibility": strict_compatibility,
            "persist": persist,
        },
    )

    warnings: list[str] = []

    try:
        if factory_id:
            if db is None:
                raise DocumentParserPipelineError(
                    "factory_lookup",
                    "Sesi database tidak tersedia untuk mode factory_id.",
                )

            dt_service = DigitalTwinService(db)
            if await dt_service.get_factory(factory_id) is None:
                raise DocumentParserPipelineError(
                    "factory_lookup",
                    f"Factory '{factory_id}' tidak ditemukan. Buat factory terlebih "
                    f"dahulu melalui POST /factories.",
                )

            factory_structure, worker_list, load_warnings = await dt_service.get_matrix_inputs(
                factory_id
            )
            warnings.extend(load_warnings)

            if not worker_list:
                raise DocumentParserPipelineError(
                    "worker_lookup",
                    f"Factory '{factory_id}' belum memiliki data pekerja. Jalankan "
                    f"POST /documents/step-4 (unggah ZIP CV) terlebih dahulu.",
                )
            if not factory_structure.get("job_desks"):
                raise DocumentParserPipelineError(
                    "job_desk_lookup",
                    f"Factory '{factory_id}' belum memiliki job desk. Simpan flowchart "
                    f"simulasi terlebih dahulu melalui POST /simulation/{factory_id}.",
                )
        else:
            factory_structure = _to_dict(factory_structure)
            worker_list = _read_worker_list(worker_profile)
            if not worker_list:
                raise DocumentParserPipelineError(
                    "worker_lookup", "'workerProfile' tidak memuat satu pun pekerja valid."
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
                progress=progress,
            )
        except CompatibilityEvaluationError as error:
            raise DocumentParserPipelineError(
                "compatibility", str(error), details=list(error.failures)
            ) from error
        except ValueError as error:
            raise DocumentParserPipelineError(
                "compatibility",
                f"Tidak ada pasangan pekerja x job desk yang bisa dievaluasi: {error}",
            ) from error
        except Exception as error:
            raise DocumentParserPipelineError(
                "compatibility", f"Gagal membuat matriks kompatibilitas: {error}"
            ) from error

        matrix_dict = matrix if isinstance(matrix, dict) else {}
        meta = matrix_dict.get("meta", {}) if isinstance(matrix_dict.get("meta"), dict) else {}
        failed_pairs = meta.get("failed_pairs", []) or []
        for failure in failed_pairs:
            warnings.append(
                f"Pasangan worker '{failure.get('worker_id')}' x job "
                f"'{failure.get('job_id')}' gagal dievaluasi agent."
            )

        flat_matrix = _flatten_compatibility_matrix(matrix)
        job_asset_map = {
            job.get("job_id"): job.get("assigned_asset_id")
            for job in (factory_structure.get("job_desks") or factory_structure.get("job_descriptions") or [])
            if isinstance(job, dict)
        }
        for entry in flat_matrix:
            if not entry.get("asset_id"):
                entry["asset_id"] = job_asset_map.get(entry.get("job_id"))

        evaluations_persisted = 0
        if factory_id and persist and db is not None:
            try:
                evaluations_persisted = await persist_compatibility_matrix(
                    db,
                    factory_id,
                    {"llm_compatibility_and_evaluations": flat_matrix},
                    valid_worker_ids={str(w["worker_id"]) for w in worker_list},
                    warnings=warnings,
                )
                await db.commit()
            except Exception as error:
                await db.rollback()
                raise DocumentParserPipelineError(
                    "ingestion",
                    f"Matriks berhasil dibuat namun gagal disimpan ke database: {error}",
                ) from error

        result = {
            "factory_id": factory_id,
            "compatibility_matrix": _to_dict(matrix) if not isinstance(matrix, list) else matrix,
            "pairs_evaluated": int(meta.get("evaluated_pairs", len(flat_matrix)) or 0),
            "evaluations_persisted": evaluations_persisted,
            "failed_pairs": list(failed_pairs),
            "warnings": warnings,
        }

        _log_json(
            "step_5_generate_compatibility_matrix",
            "SUCCESS",
            output={
                "factory_id": factory_id,
                "pairs_evaluated": result["pairs_evaluated"],
                "evaluations_persisted": evaluations_persisted,
            },
        )
        return result

    except DocumentParserPipelineError as err:
        _log_error("step_5_generate_compatibility_matrix", err, payload={"stage": err.stage})
        raise
    except Exception as err:
        _log_error("step_5_generate_compatibility_matrix", err)
        raise


# --------------------------------------------------------------------------
# Fungsi Kombinasi (Otomatis): Tahap 1, 2, 4, & 5 (Persisted via Repository)
# --------------------------------------------------------------------------

async def process_combined_documents_pipeline(
    template: UploadFile,
    worker_zip: UploadFile,
    db: AsyncSession | None = None,
    strict: bool = False,
    max_workers: int = 4,
    max_attempts: int = 3,
    factory_id: str | None = None,
) -> dict[str, Any]:
    """
    Eksekusi penuh pipeline terpadu dari Tahap 1 hingga Tahap 5, berdasarkan upload
    file PDF/DOCX/dsb (template) & ZIP (worker_zip).
    Merekam audit log ke `DocumentParseJob` dan melakukan persistence ke DB via `repository.py`.
    """
    filename_template = template.filename or "template.pdf"
    filename_worker = worker_zip.filename or "workers.zip"

    _log_json(
        "process_combined_documents_pipeline",
        "START",
        payload={
            "template": filename_template,
            "worker_zip": filename_worker,
            "strict": strict,
            "max_workers": max_workers,
            "max_attempts": max_attempts,
        },
    )

    _validate_suffix(filename_template, TEMPLATE_SUFFIXES, "template")
    _validate_suffix(filename_worker, WORKER_SUFFIXES, "worker_zip")

    combined_warnings: list[str] = []

    try:
        # Step 1 + 2: Pipeline Dokumen Pabrik
        _log_json("process_combined_documents_pipeline.stage_1_2", "START")
        factory_result = await process_factory_document_pipeline(
            template, db=None, factory_id=factory_id
        )
        fac_structure_dict = _to_dict(factory_result["factory_structure"])
        resolved_factory_id = assign_canonical_factory_id(fac_structure_dict, factory_id)

        if factory_result.get("extraction_summary", {}).get("warnings"):
            combined_warnings.extend(factory_result["extraction_summary"]["warnings"])
        _log_json("process_combined_documents_pipeline.stage_1_2", "SUCCESS")

        # Step 4: Profil Pekerja
        _log_json("process_combined_documents_pipeline.stage_4", "START")
        worker_result = await step_4_extract_worker_profiles(
            worker_zip=worker_zip,
            strict=strict,
            max_workers=max_workers,
            max_attempts=max_attempts,
        )
        worker_profile = worker_result["worker_profile"]
        _log_json("process_combined_documents_pipeline.stage_4", "SUCCESS")

        # Step 5: Matriks Kompatibilitas
        _log_json("process_combined_documents_pipeline.stage_5", "START")
        compatibility_result = await step_5_generate_compatibility_matrix(
            factory_structure=fac_structure_dict,
            worker_profile=worker_profile,
            max_workers=max_workers,
            max_attempts=max_attempts,
            strict_compatibility=strict,
        )
        compatibility_matrix = compatibility_result["compatibility_matrix"]
        if compatibility_result.get("warnings"):
            combined_warnings.extend(compatibility_result["warnings"])
        _log_json("process_combined_documents_pipeline.stage_5", "SUCCESS")

        # Validasi struktur Digital Twin
        _log_json("process_combined_documents_pipeline.build_digital_twin", "START")
        dt_model = build_digital_twin_from_results(
            factory_structure=fac_structure_dict,
            worker_profile=worker_profile,
            compatibility_matrix=compatibility_matrix,
            warnings=combined_warnings,
        )
        _log_json("process_combined_documents_pipeline.build_digital_twin", "SUCCESS")

        # Ingestion & audit trail log ke Database via repository.py
        parse_job_id = None
        if db is not None:
            _log_json("process_combined_documents_pipeline.persist", "START")
            try:
                persist_res = await persist_completed_pipeline(
                    session=db,
                    factory_structure=fac_structure_dict,
                    worker_profile=worker_profile,
                    compatibility_matrix=compatibility_matrix,
                    template_filename=filename_template,
                    cv_bundle_filename=filename_worker,
                    warnings=dt_model.warnings,
                )
                parse_job_id = persist_res.get("job_id")
                _log_json("process_combined_documents_pipeline.persist", "SUCCESS", output=persist_res)
            except Exception as persist_err:
                _log_error("process_combined_documents_pipeline.persist", persist_err)
                raise DocumentParserPipelineError(
                    "ingestion", f"Gagal melakukan persistence ke DB: {persist_err}"
                ) from persist_err

        final_response = {
            "parse_job_id": parse_job_id,
            "factory_id": resolved_factory_id,
            "extraction_summary": factory_result.get("extraction_summary", {}),
            "agent_input": factory_result.get("agent_input", ""),
            "factory_structure": fac_structure_dict,
            "worker_profile": _to_dict(worker_profile),
            "worker_agent_input": worker_result.get("worker_agent_input", ""),
            "candidates_found": worker_result.get("candidates_found", 0),
            "rejected_blocks_count": worker_result.get("rejected_blocks_count", 0),
            "archive_reports": worker_result.get("archive_reports", []),
            "compatibility_matrix": _to_dict(compatibility_matrix) if not isinstance(compatibility_matrix, list) else compatibility_matrix,
            "digital_twin": dt_model,
        }

        _log_json(
            "process_combined_documents_pipeline",
            "SUCCESS",
            output={
                "parse_job_id": parse_job_id,
                "warnings_count": len(dt_model.warnings),
            },
        )

        return final_response

    except DocumentParserPipelineError as err:
        _log_error("process_combined_documents_pipeline", err, payload={"stage": err.stage})
        if db is not None:
            await record_failed_parse_job(
                session=db,
                error=err,
                template_filename=filename_template,
                cv_bundle_filename=filename_worker,
            )
        raise err
    except Exception as err:
        _log_error("process_combined_documents_pipeline", err)
        if db is not None:
            pipeline_err = DocumentParserPipelineError("unknown", str(err))
            await record_failed_parse_job(
                session=db,
                error=pipeline_err,
                template_filename=filename_template,
                cv_bundle_filename=filename_worker,
            )
        raise err


# --------------------------------------------------------------------------
# Fungsi Kombinasi (MANUAL): Tahap 1, 2, 4, & 5 dari payload form frontend
# --------------------------------------------------------------------------

async def _check_factory_id_conflict(
    db: AsyncSession, factory_id: str, overwrite: bool
) -> str | None:
    """
    Node D01_VALIDASI_FACTORY_ID: cek apakah factory_id sudah terdaftar.
    Mengembalikan pesan error (str) bila konflik, atau None bila boleh lanjut.
    """
    existing = await db.get(Factory, factory_id)
    if existing is not None and not overwrite:
        return (
            f"ID Pabrik '{factory_id}' sudah terdaftar. Gunakan ID lain, atau kirim "
            f"'overwriteExistingFactory: true' pada payload bila memang bermaksud "
            f"memperbarui data pabrik yang sudah ada."
        )
    return None


def _validate_manual_payload_offline(
    payload: schemas.ProcessCombinedDocumentsManualRequest,
) -> list[str]:
    """
    Node D02_VALIDASI_ASSET s/d D08_VALIDASI_EVAL: validasi silang FK & aturan bisnis
    di memori (tanpa perlu hit DB), sesuai spesifikasi-flowchart-form-manual.md.
    Mengembalikan daftar pesan error; kosong berarti payload valid.
    """
    errors: list[str] = []

    asset_ids = [a.asset_id for a in payload.assets]
    stage_ids = [s.stage_id for s in payload.process_stages]
    shift_ids = [s.shift_id for s in payload.shifts]
    job_ids = [j.job_id for j in payload.job_desks]
    worker_ids = [w.worker_id for w in payload.workers]

    asset_id_set = set(asset_ids)
    stage_id_set = set(stage_ids)
    shift_id_set = set(shift_ids)
    job_id_set = set(job_ids)
    worker_id_set = set(worker_ids)

    # --- D02_VALIDASI_ASSET ---
    if len(asset_ids) != len(asset_id_set):
        dupes = sorted({x for x in asset_ids if asset_ids.count(x) > 1})
        errors.append(f"D02_VALIDASI_ASSET: asset_id duplikat dalam payload: {', '.join(dupes)}")
    for a in payload.assets:
        for field_name in ("capacity_per_unit", "total_capacity"):
            cap = getattr(a, field_name)
            if cap is not None and (cap.value is None) != (cap.unit is None):
                errors.append(
                    f"D02_VALIDASI_ASSET: aset '{a.asset_id}' field '{field_name}' harus "
                    f"mengisi value & unit sekaligus, atau kosongkan keduanya."
                )

    # --- D03_VALIDASI_STAGE ---
    if len(stage_ids) != len(stage_id_set):
        dupes = sorted({x for x in stage_ids if stage_ids.count(x) > 1})
        errors.append(f"D03_VALIDASI_STAGE: stage_id duplikat dalam payload: {', '.join(dupes)}")
    for s in payload.process_stages:
        if s.asset_id not in asset_id_set:
            errors.append(
                f"D03_VALIDASI_STAGE: stage '{s.stage_id}' mereferensikan asset_id "
                f"'{s.asset_id}' yang belum terdaftar pada daftar 'assets'."
            )
        if s.next_stage_id and s.next_stage_id not in stage_id_set:
            errors.append(
                f"D03_VALIDASI_STAGE: stage '{s.stage_id}' memiliki next_stage_id "
                f"'{s.next_stage_id}' yang tidak ditemukan pada daftar 'process_stages'."
            )

    # --- D04_VALIDASI_GRAPH ---
    info = payload.factory_info
    for ref_field, ref_values in (
        ("workflowSequence", info.workflow_sequence),
        ("entryStages", info.entry_stages),
        ("terminalStages", info.terminal_stages),
    ):
        unknown = [v for v in ref_values if v not in stage_id_set]
        if unknown:
            errors.append(
                f"D04_VALIDASI_GRAPH: field '{ref_field}' berisi stage_id tidak dikenal: "
                f"{', '.join(unknown)}"
            )
    for edge in info.process_edges:
        frm = edge.get("from_stage") or edge.get("from")
        to = edge.get("to_stage") or edge.get("to")
        if frm not in stage_id_set or to not in stage_id_set:
            errors.append(
                f"D04_VALIDASI_GRAPH: 'processEdges' berisi stage_id tidak dikenal: {edge}"
            )
    used_lanes = {s.lane for s in payload.process_stages}
    missing_lanes = used_lanes - set(info.lanes)
    if missing_lanes:
        errors.append(
            f"D04_VALIDASI_GRAPH: lane berikut dipakai oleh process_stages tapi belum "
            f"didaftarkan di factory_info.lanes: {', '.join(sorted(missing_lanes))}"
        )

    # --- D05_VALIDASI_SHIFT ---
    if len(shift_ids) != len(shift_id_set):
        dupes = sorted({x for x in shift_ids if shift_ids.count(x) > 1})
        errors.append(f"D05_VALIDASI_SHIFT: shift_id duplikat dalam payload: {', '.join(dupes)}")

    # --- D06_VALIDASI_JOB_DESK ---
    if len(job_ids) != len(job_id_set):
        dupes = sorted({x for x in job_ids if job_ids.count(x) > 1})
        errors.append(f"D06_VALIDASI_JOB_DESK: job_id duplikat dalam payload: {', '.join(dupes)}")
    for j in payload.job_desks:
        if j.stage_id not in stage_id_set:
            errors.append(
                f"D06_VALIDASI_JOB_DESK: job '{j.job_id}' stage_id '{j.stage_id}' tidak "
                f"ditemukan pada daftar 'process_stages'."
            )
        if j.assigned_asset_id not in asset_id_set:
            errors.append(
                f"D06_VALIDASI_JOB_DESK: job '{j.job_id}' assigned_asset_id "
                f"'{j.assigned_asset_id}' tidak ditemukan pada daftar 'assets'."
            )
        if j.shift_id not in shift_id_set:
            errors.append(
                f"D06_VALIDASI_JOB_DESK: job '{j.job_id}' shift_id '{j.shift_id}' tidak "
                f"ditemukan pada daftar 'shifts'."
            )
        for wid in j.assigned_worker_ids:
            if wid not in worker_id_set:
                errors.append(
                    f"D06_VALIDASI_JOB_DESK: job '{j.job_id}' assigned_worker_ids berisi "
                    f"'{wid}' yang tidak ditemukan pada daftar 'workers'."
                )

    # --- D07_VALIDASI_WORKER ---
    if len(worker_ids) != len(worker_id_set):
        dupes = sorted({x for x in worker_ids if worker_ids.count(x) > 1})
        errors.append(f"D07_VALIDASI_WORKER: worker_id duplikat dalam payload: {', '.join(dupes)}")

    # --- D08_VALIDASI_EVAL ---
    eval_seen: set[tuple[str, str]] = set()
    for e in payload.compatibility_evaluations:
        if e.worker_id not in worker_id_set:
            errors.append(
                f"D08_VALIDASI_EVAL: worker_id '{e.worker_id}' tidak ditemukan pada daftar 'workers'."
            )
        if e.job_id not in job_id_set:
            errors.append(
                f"D08_VALIDASI_EVAL: job_id '{e.job_id}' tidak ditemukan pada daftar 'job_desks'."
            )
        if e.asset_id and e.asset_id not in asset_id_set:
            errors.append(
                f"D08_VALIDASI_EVAL: asset_id '{e.asset_id}' tidak ditemukan pada daftar 'assets'."
            )
        key = (e.worker_id, e.job_id)
        if key in eval_seen:
            errors.append(
                f"D08_VALIDASI_EVAL: evaluasi duplikat untuk worker '{e.worker_id}' x job '{e.job_id}'."
            )
        eval_seen.add(key)

    return errors


def _normalize_shift(shift: schemas.ShiftManualInput) -> dict[str, Any]:
    """
    Node N05_INPUT_SHIFT (bagian transformasi): mengisi otomatis `duration_hours`
    dan `crosses_midnight` bila tidak diisi user, berdasarkan start_time/end_time.
    """
    start_h, start_m = (int(x) for x in shift.start_time.split(":"))
    end_h, end_m = (int(x) for x in shift.end_time.split(":"))
    start_total = start_h * 60 + start_m
    end_total = end_h * 60 + end_m

    crosses_midnight = shift.crosses_midnight
    if crosses_midnight is None:
        crosses_midnight = end_total <= start_total

    if shift.duration_hours is not None:
        duration_hours = shift.duration_hours
    else:
        delta_minutes = (
            (end_total - start_total)
            if not crosses_midnight
            else (end_total + 24 * 60 - start_total)
        )
        duration_hours = round(delta_minutes / 60, 2)

    data = shift.model_dump()
    data["crosses_midnight"] = crosses_midnight
    data["duration_hours"] = duration_hours
    return data


def _fill_capacity_raw(cap: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mengisi field `raw` otomatis dari value+unit bila kosong (capacity_per_unit/total_capacity/throughput)."""
    if not cap:
        return cap
    if not cap.get("raw") and cap.get("value") is not None and cap.get("unit"):
        cap["raw"] = f"{cap['value']} {cap['unit']}"
    return cap


def _manual_payload_to_pipeline_inputs(
    payload: schemas.ProcessCombinedDocumentsManualRequest,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """
    Node N04 (Process/Transformasi): mengonversi payload manual (Pydantic) menjadi
    struktur `twin` / `worker_profile` / `evaluations` dengan bentuk yang SAMA dengan
    output alur otomatis, sehingga bisa langsung dipakai ulang oleh
    `build_digital_twin_from_results()` dan `persist_completed_pipeline()`.
    """
    factory_info = payload.factory_info.model_dump()

    assets = [a.model_dump() for a in payload.assets]
    for a in assets:
        a["capacity_per_unit"] = _fill_capacity_raw(a.get("capacity_per_unit"))
        a["total_capacity"] = _fill_capacity_raw(a.get("total_capacity"))

    stages = [s.model_dump() for s in payload.process_stages]
    for s in stages:
        s["throughput"] = _fill_capacity_raw(s.get("throughput"))

    shifts = [_normalize_shift(s) for s in payload.shifts]
    job_desks = [j.model_dump() for j in payload.job_desks]
    workers = [w.model_dump() for w in payload.workers]
    evaluations = [e.model_dump() for e in payload.compatibility_evaluations]

    twin = {
        "factory_info": factory_info,
        "assets": assets,
        "process_stages": stages,
        "shifts": shifts,
        "job_desks": job_desks,
    }
    worker_profile = {"workers": workers}
    return twin, worker_profile, evaluations


async def process_combined_documents_manual_pipeline(
    payload: schemas.ProcessCombinedDocumentsManualRequest,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Versi MANUAL dari Kombinasi Tahap 1, 2, 4, & 5 -- menerima seluruh data pabrik,
    aset, tahapan proses, shift, job desk, pekerja, dan evaluasi kompatibilitas
    langsung dari form frontend (menggantikan upload `template` PDF & `worker_zip`).

    Urutan node mengikuti spesifikasi-flowchart-form-manual.md:
    D01 (factory_id unik) -> D02-D08 (validasi silang FK & aturan bisnis, di memori)
    -> N04 (transformasi payload -> twin) -> build_digital_twin_from_results()
    -> persist_completed_pipeline() (satu transaksi DB).

    Karena seluruh FK sudah divalidasi SEBELUM data sampai ke `persist_completed_pipeline`,
    kegagalan seperti `stage_id` kosong seharusnya sudah tertangkap di D06, bukan lolos
    sebagai `IntegrityError` dari Postgres seperti pada alur otomatis sebelumnya.
    """
    factory_id = payload.factory_info.factory_id

    _log_json(
        "process_combined_documents_manual_pipeline",
        "START",
        payload={
            "factory_id": factory_id,
            "assets_count": len(payload.assets),
            "process_stages_count": len(payload.process_stages),
            "shifts_count": len(payload.shifts),
            "job_desks_count": len(payload.job_desks),
            "workers_count": len(payload.workers),
            "compatibility_evaluations_count": len(payload.compatibility_evaluations),
        },
    )

    try:
        # D01_VALIDASI_FACTORY_ID
        conflict_msg = await _check_factory_id_conflict(
            db, factory_id, payload.overwrite_existing_factory
        )
        if conflict_msg:
            raise DocumentParserPipelineError("D01_VALIDASI_FACTORY_ID", conflict_msg)

        # D02_VALIDASI_ASSET s/d D08_VALIDASI_EVAL
        errors = _validate_manual_payload_offline(payload)
        if errors:
            err = DocumentParserPipelineError(
                "validation",
                f"Ditemukan {len(errors)} kesalahan validasi pada data manual. "
                f"Lihat 'details' untuk rincian per-node.",
            )
            err.details = errors
            raise err

        # N04: transformasi payload manual -> struktur twin/worker_profile/evaluations
        twin, worker_profile, evaluations = _manual_payload_to_pipeline_inputs(payload)

        combined_warnings: list[str] = []

        _log_json("process_combined_documents_manual_pipeline.build_digital_twin", "START")
        dt_model = build_digital_twin_from_results(
            factory_structure=twin,
            worker_profile=worker_profile,
            compatibility_matrix=evaluations,
            warnings=combined_warnings,
        )
        _log_json("process_combined_documents_manual_pipeline.build_digital_twin", "SUCCESS")

        _log_json("process_combined_documents_manual_pipeline.persist", "START")
        persist_res = await persist_completed_pipeline(
            session=db,
            factory_structure=twin,
            worker_profile=worker_profile,
            compatibility_matrix=evaluations,
            template_filename="manual_input",
            cv_bundle_filename="manual_input",
            warnings=dt_model.warnings,
        )
        _log_json(
            "process_combined_documents_manual_pipeline.persist", "SUCCESS", output=persist_res
        )

        result = {
            "parse_job_id": persist_res.get("job_id"),
            "factory_id": persist_res.get("factory_id"),
            "workers_parsed": persist_res.get("workers_parsed", 0),
            "job_desks_parsed": persist_res.get("job_desks_parsed", 0),
            "warnings": persist_res.get("warnings", []),
        }

        _log_json("process_combined_documents_manual_pipeline", "SUCCESS", output=result)
        return result

    except DocumentParserPipelineError as err:
        _log_error(
            "process_combined_documents_manual_pipeline",
            err,
            payload={"stage": err.stage, "details": getattr(err, "details", None)},
        )
        await record_failed_parse_job(
            session=db,
            error=err,
            template_filename="manual_input",
            cv_bundle_filename="manual_input",
            factory_id=factory_id,
        )
        raise
    except Exception as err:
        _log_error("process_combined_documents_manual_pipeline", err)
        pipeline_err = DocumentParserPipelineError("unknown", str(err))
        await record_failed_parse_job(
            session=db,
            error=pipeline_err,
            template_filename="manual_input",
            cv_bundle_filename="manual_input",
            factory_id=factory_id,
        )
        raise pipeline_err from err


async def get_parsed_factories_list(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Mengambil daftar pabrik yang berhasil diparsing beserta ID Job audit lognya."""
    stmt = (
        select(DocumentParseJob)
        .where(DocumentParseJob.status == "success")
        .order_by(DocumentParseJob.id.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    factories = []
    for job in jobs:
        fac_struct = job.factory_structure or {}
        fac_info = fac_struct.get("factory_info", {})

        workers = job.worker_profile.get("workers", []) if isinstance(job.worker_profile, dict) else []
        job_desks = fac_struct.get("job_desks") or fac_struct.get("job_descriptions") or []

        factories.append({
            "factoryId": fac_info.get("factory_id") or job.factory_id or f"FAC-{job.id}",
            "factoryName": fac_info.get("factory_name") or "Pabrik Tanpa Nama",
            "workersCount": job.workers_parsed or len(workers),
            "jobDesksCount": job.job_desks_parsed or len(job_desks),
            "createdAt": job.created_at.isoformat() if hasattr(job, "created_at") and job.created_at else None,
            "jobId": str(job.id),  # <-- Sertakan ID Job di sini (konversi ke string)
        })

    return factories