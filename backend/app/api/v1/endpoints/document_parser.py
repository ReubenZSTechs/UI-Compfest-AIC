"""
backend/app/api/v1/endpoints/document_parser.py

Endpoint pemrosesan dokumen pabrik & worker (Pipeline Terpadu, Kombinasi 1-5, & Tahap 3 s/d 5).
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.modules.documents import service
from app.modules.documents.exceptions import DocumentParserPipelineError
from app.modules.documents.schemas import (
    ProcessCombinedDocumentsResponse,
    ProcessFactoryDocumentResponse,
    Step3Request,
    Step3Response,
    Step4Response,
    Step5Request,
    Step5Response,
)

router = APIRouter()


def _handle_error(err: DocumentParserPipelineError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"stage": err.stage, "message": err.message, "details": err.details},
    )


# --- Endpoint Tahap 1 & 2 Terpadu ---

@router.post(
    "/process-factory-document",
    response_model=ProcessFactoryDocumentResponse,
    summary="Tahap 1 & 2 Terpadu: Ekstraksi Dokumen & Generasi Struktur Pabrik",
)
async def process_factory_document(
    template: UploadFile = File(..., description="Dokumen template pabrik (.pdf, .docx, .md, .txt)"),
) -> ProcessFactoryDocumentResponse:
    """Menerima berkas template pabrik, mengekstraksi data tabel/teks, dan mengeksekusi Agent A."""
    try:
        return await service.process_factory_document_pipeline(template)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Kombinasi Tahap 1-2, Tahap 4, & Tahap 5 ---

@router.post(
    "/process-combined-documents",
    response_model=ProcessCombinedDocumentsResponse,
    summary="Kombinasi Tahap 1, 2, 4, & 5: Pemrosesan Dokumen Pabrik, ZIP Pekerja, & Matriks Kompatibilitas Sekaligus",
)
async def process_combined_documents(
    template: UploadFile = File(..., description="Dokumen template pabrik (.pdf, .docx, .md, .txt)"),
    worker_zip: UploadFile = File(..., description="Arsip ZIP berisi CV/catatan pekerja (.zip)"),
    strict: bool = Query(
        False,
        description="Jika true, hentikan proses bila ada berkas dalam ZIP yang gagal diekstraksi",
    ),
    max_workers: int = Query(
        4,
        description="Jumlah pekerja maksimum yang diproses dalam matriks kompatibilitas",
    ),
    max_attempts: int = Query(
        3,
        description="Jumlah batas percobaan ulang evaluasi kompatibilitas",
    ),
) -> ProcessCombinedDocumentsResponse:
    """
    Menerima dokumen pabrik dan ZIP CV pekerja secara bersamaan, mengekstraksi data,
    mengeksekusi Agent A (Struktur Pabrik), Agent B (Profil Pekerja), serta generasi
    Matriks Kompatibilitas (Tahap 5) dalam satu alur terpadu.
    """
    try:
        result = await service.process_combined_documents_pipeline(
            template=template,
            worker_zip=worker_zip,
            strict=strict,
            max_workers=max_workers,
            max_attempts=max_attempts,
        )
        return ProcessCombinedDocumentsResponse(**result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Tahap 4 (ZIP & Profil Pekerja) ---

@router.post(
    "/step-4",
    response_model=Step4Response,
    response_model_by_alias=True,
    summary="Tahap 4: Ekstraksi ZIP CV & Agent B (Profil Pekerja)",
)
async def extract_worker_profiles(
    worker_zip: UploadFile = File(
        ..., description="Berkas arsip .zip berisi CV/catatan wawancara pekerja"
    ),
    strict: bool = Query(
        False,
        description="Jika true, hentikan proses bila ada berkas dalam ZIP yang gagal diekstraksi",
    ),
) -> Step4Response:
    """
    Menerima berkas ZIP berisi dokumen CV/catatan wawancara pekerja (.pdf, .docx, .md, .txt),
    mengekstraksi konten arsip, dan memanggil Agent B untuk merestrukturisasi profil worker.
    """
    try:
        result = await service.step_4_extract_worker_profiles(worker_zip, strict=strict)
        return Step4Response(**result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Tahap 5 (Matriks Kompatibilitas) ---

@router.post(
    "/step-5",
    response_model=Step5Response,
    response_model_by_alias=True,
    summary="Tahap 5: Matriks Kompatibilitas Pekerja x Job Desk",
)
async def generate_compatibility_matrix(
    payload: Step5Request,
) -> Step5Response:
    """Mengevaluasi kesesuaian antara struktur pabrik dan profil pekerja."""
    try:
        result = await service.step_5_generate_compatibility_matrix(
            factory_structure=payload.factory_structure,
            worker_profile=payload.worker_profile,
            max_workers=payload.max_workers,
            max_attempts=payload.max_attempts,
            strict_compatibility=payload.strict_compatibility,
        )
        return Step5Response(**result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err