"""
backend/app/modules/documents/service.py

Layanan modul document-parser terisolasi (Tahap 1+2 Terpadu, Tahap 4, Tahap 5, & Kombinasi 1-5).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

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


# --- Tahap 1 & 2 Terpadu: Ekstraksi Dokumen & Generasi Struktur Pabrik ---

async def process_factory_document_pipeline(template: UploadFile) -> dict[str, Any]:
    """
    Menggabungkan Tahap 1 (Ekstraksi Dokumen Pabrik) dan Tahap 2 (Agent A)
    menjadi satu kesatuan alur proses.
    """
    filename = template.filename or "template.pdf"
    _validate_suffix(filename, TEMPLATE_SUFFIXES, "template")

    warnings: list[str] = []

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

    # 4. Return Hasil Terpadu
    return {
        "extraction_summary": {
            "extracted_fields": document.text_fields,
            "tables_count": len(document.tables),
            "raw_text": document.raw_text,
            "warnings": warnings,
        },
        "agent_input": agent_input,
        "factory_structure": twin,
    }


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
    # 1. Ekstrak list pekerja dari dict worker_profile
    worker_list = worker_profile.get("workers", [])

    # 2. Ambil agent pencocokan dari registry
    registry = get_agent_registry()
    compatibility_agent = registry.get(AgentRole.WORKER_COMPATIBILITY)

    # 3. Eksekusi evaluasi kompatibilitas
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


# --- Fungsi Kombinasi: Tahap 1+2, Tahap 4, & Tahap 5 ---

async def process_combined_documents_pipeline(
    template: UploadFile,
    worker_zip: UploadFile,
    strict: bool = False,
    max_workers: int = 4,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """
    Menggabungkan pemrosesan dokumen pabrik (Tahap 1+2), pemrosesan ZIP CV worker (Tahap 4),
    dan pembentukan matriks kompatibilitas (Tahap 5) dalam satu alur eksekusi sekaligus.
    """
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

    return {
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