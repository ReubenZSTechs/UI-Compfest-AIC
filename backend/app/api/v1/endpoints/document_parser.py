# backend/app/api/v1/endpoints/document_parser.py
"""
Endpoint pemrosesan dokumen pabrik & worker (Pipeline Terpadu, Kombinasi 1-5, & Tahap 3 s/d 5).
Sesuai dengan Standar Kontrak Data Digital Twin System.

Perubahan pada revisi ini:
1. DITAMBAHKAN: `POST /process-combined-documents-manual` -- versi Kombinasi Tahap 1, 2, 4,
   & 5 yang menerima payload JSON langsung dari form frontend (menggantikan upload
   `template` PDF & `worker_zip` ZIP), sesuai spesifikasi-flowchart-form-manual.md.
   Seluruh validasi silang FK (D01-D08) dilakukan di service layer sebelum data
   disimpan, sehingga kesalahan seperti stage_id/asset_id/shift_id kosong dilaporkan
   sebagai HTTP 422 dengan rincian per-node, bukan lolos sebagai IntegrityError.
2. `/process-combined-documents` (alur otomatis PDF/ZIP) TIDAK diubah endpoint-nya --
   tetap dipertahankan untuk kompatibilitas, kini memakai repository.py yang sudah
   diperbaiki (persist ProcessStage & Shift yang sebelumnya hilang).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.modules.documents import service
from app.modules.documents.exceptions import DocumentParserPipelineError
from app.worker import tasks as worker_tasks

from app.modules.documents.schemas import (
    CompatibilityJobRequest,
    CompatibilityJobResponse,
    ParseJobResult,
    ProcessCombinedDocumentsManualRequest,
    ProcessCombinedDocumentsManualResponse,
    ProcessCombinedDocumentsResponse,
    ProcessFactoryDocumentResponse,
    Step3Request,
    Step3Response,
    Step4Response,
    Step5Request,
    Step5Response,
    FactoryListItemResponse
)

router = APIRouter()


def _handle_error(err: DocumentParserPipelineError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "stage": err.stage,
            "message": str(err),
            "details": getattr(err, "details", None) or str(err),
        },
    )


# --- Endpoint Tahap 1 & 2 Terpadu ---

@router.post(
    "/process-factory-document",
    response_model=ProcessFactoryDocumentResponse,
    response_model_by_alias=True,
    summary="Tahap 1 & 2 Terpadu: Ekstraksi Dokumen & Generasi Struktur Pabrik",
)
async def process_factory_document(
    # FIX: Update dokumentasi endpoint untuk memasukkan .xlsx, .xls, .csv
    template: UploadFile = File(..., description="Dokumen template pabrik (.xlsx, .xls, .csv, .pdf, .docx, .md, .txt)"),
    db: AsyncSession = Depends(get_db),
) -> ProcessFactoryDocumentResponse:
    """Menerima berkas template pabrik, mengekstraksi data tabel/teks, mengeksekusi Agent A, dan meng-ingest log/data."""
    try:
        result = await service.process_factory_document_pipeline(template, db=db)
        return ProcessFactoryDocumentResponse.model_validate(result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Kombinasi Tahap 1-2, Tahap 4, & Tahap 5 (ALUR OTOMATIS: PDF + ZIP) ---

@router.post(
    "/process-combined-documents",
    response_model=ProcessCombinedDocumentsResponse,
    response_model_by_alias=True,
    summary="Kombinasi Tahap 1, 2, 4, & 5: Pemrosesan Dokumen Pabrik, ZIP Pekerja, & Matriks Kompatibilitas Sekaligus",
)
async def process_combined_documents(
    # FIX: Update dokumentasi endpoint untuk memasukkan .xlsx, .xls, .csv
    template: UploadFile = File(..., description="Dokumen template pabrik (.xlsx, .xls, .csv, .pdf, .docx, .md, .txt)"),
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
    factory_id: str | None = Query(
        None,
        description=(
            "Tautkan hasil parsing ke factory yang sudah ada (POST /factories). "
            "Dikosongkan berarti factory_id kanonik baru akan dibuat otomatis."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> ProcessCombinedDocumentsResponse:
    """
    Menerima dokumen pabrik dan ZIP CV pekerja secara bersamaan, mengekstraksi data,
    mengeksekusi Agent A (Struktur Pabrik), Agent B (Profil Pekerja), serta generasi
    Matriks Kompatibilitas (Tahap 5) dalam satu alur terpadu. Hasilnya langsung tersimpan ke Digital Twin DB.

    Catatan: untuk input MANUAL (form frontend, tanpa upload PDF/ZIP), gunakan
    `POST /process-combined-documents-manual` di bawah.
    """
    try:
        result = await service.process_combined_documents_pipeline(
            template=template,
            worker_zip=worker_zip,
            db=db,
            strict=strict,
            max_workers=max_workers,
            max_attempts=max_attempts,
            factory_id=factory_id,
        )
        return ProcessCombinedDocumentsResponse.model_validate(result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Kombinasi Tahap 1-2, Tahap 4, & Tahap 5 (ALUR MANUAL: Form Frontend) ---

@router.post(
    "/process-combined-documents-manual",
    response_model=ProcessCombinedDocumentsManualResponse,
    response_model_by_alias=True,
    summary="Kombinasi Tahap 1, 2, 4, & 5 (Input Manual via Form Frontend)",
)
async def process_combined_documents_manual(
    payload: ProcessCombinedDocumentsManualRequest,
    db: AsyncSession = Depends(get_db),
) -> ProcessCombinedDocumentsManualResponse:
    """
    Menerima seluruh data pabrik (Factory), aset, tahapan proses, shift, job desk,
    pekerja, dan evaluasi kompatibilitas langsung sebagai payload JSON dari form
    frontend -- menggantikan upload `template` (PDF/DOCX/dsb) & `worker_zip` (ZIP)
    pada `/process-combined-documents`.

    Seluruh relasi FK antar-entitas (stage_id, assigned_asset_id, shift_id, worker_id,
    job_id, dst.) divalidasi di memori terlebih dahulu (setara node D01-D08 pada
    spesifikasi-flowchart-form-manual.md) sebelum data dicoba disimpan ke Digital Twin
    DB dalam satu transaksi. Bila validasi gagal, response 422 akan memuat `stage`
    (nama node yang gagal, mis. `D06_VALIDASI_JOB_DESK`) dan `details` berisi daftar
    pesan kesalahan per-item sehingga frontend bisa menyorot field yang bermasalah.

    Set `overwriteExistingFactory: true` pada payload bila bermaksud memperbarui
    data pabrik yang factory_id-nya sudah terdaftar (bukan membuat baru).
    """
    try:
        result = await service.process_combined_documents_manual_pipeline(
            payload=payload,
            db=db,
        )
        return ProcessCombinedDocumentsManualResponse.model_validate(result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Tahap 3 (Validasi Kesenjangan Struktur Pabrik) ---

@router.post(
    "/step-3",
    response_model=Step3Response,
    response_model_by_alias=True,
    summary="Tahap 3: Validasi Kesenjangan Struktur Pabrik",
)
async def validate_factory_structure_gaps(
    payload: Step3Request,
) -> Step3Response:
    """Mengevaluasi kelengkapan bidang data pada struktur pabrik hasil ekstraksi Agent A."""
    try:
        factory_dict = payload.factory_structure
        job_desks = factory_dict.get("job_desks") or factory_dict.get("job_descriptions") or []
        assets = factory_dict.get("assets", [])

        blocking = []
        warnings = []

        if not job_desks:
            blocking.append("Struktur pabrik tidak memuat entitas 'job_desks'.")
        if not assets:
            warnings.append("Daftar aset pabrik kosong.")

        return Step3Response(
            is_valid=len(blocking) == 0,
            blocking_gaps=blocking,
            warning_gaps=warnings,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal memvalidasi struktur pabrik: {err}",
        ) from err


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
    factory_id: str | None = Query(
        None,
        description=(
            "ID pabrik hasil POST /factories. Bila diisi, hasil ekstraksi langsung "
            "disimpan ke tabel `workers` dengan FK ke factory tersebut."
        ),
    ),
    strict: bool = Query(
        False,
        description="Jika true, hentikan proses bila ada berkas dalam ZIP yang gagal diekstraksi",
    ),
    max_workers: int = Query(4, ge=1, le=32),
    max_attempts: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> Step4Response:
    """
    Menerima berkas ZIP berisi dokumen CV/catatan wawancara pekerja (.pdf, .docx, .md, .txt),
    mengekstraksi konten arsip, memanggil Agent B untuk merestrukturisasi profil worker,
    lalu (bila `factory_id` diisi) menyimpannya ke Digital Twin DB.

    Baris worker yang tidak lengkap tidak langsung ditolak: worker_id kosong diberi ID
    otomatis dan field demografi yang hilang diisi nilai default, dengan setiap koreksi
    dilaporkan pada `warnings`.
    """
    try:
        result = await service.step_4_extract_worker_profiles(
            worker_zip,
            strict=strict,
            max_workers=max_workers,
            max_attempts=max_attempts,
            factory_id=factory_id,
            db=db,
        )
        return Step4Response.model_validate(result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


@router.post(
    "/step-5",
    response_model=Step5Response,
    response_model_by_alias=True,
    summary="Tahap 5: Matriks Kompatibilitas Pekerja x Job Desk",
)
async def generate_compatibility_matrix(
    payload: Step5Request,
    db: AsyncSession = Depends(get_db),
) -> Step5Response:
    """
    Mengevaluasi kesesuaian antara struktur pabrik dan profil pekerja.

    Mode utama (tombol "make digitaltwin"): kirim `factoryId` saja -- job desk hasil
    flowchart manual dan worker hasil Tahap 4 dibaca dari DB, lalu matriks yang
    dihasilkan dipersist ke `compatibility_evaluations` milik factory tersebut.
    Mode stateless lama (`factoryStructure` + `workerProfile`) tetap didukung.
    """
    try:
        result = await service.step_5_generate_compatibility_matrix(
            factory_structure=payload.factory_structure,
            worker_profile=payload.worker_profile,
            max_workers=payload.max_workers,
            max_attempts=payload.max_attempts,
            strict_compatibility=payload.strict_compatibility,
            factory_id=payload.factory_id,
            db=db,
            persist=payload.persist,
        )
        return Step5Response.model_validate(result)
    except DocumentParserPipelineError as err:
        raise _handle_error(err) from err


# --- Endpoint Tahap 5 Asinkron (Background Worker + Polling) ---

@router.post(
    "/step-5/jobs",
    response_model=CompatibilityJobResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Tahap 5 (Asinkron): Jadwalkan pembuatan matriks kompatibilitas",
)
async def enqueue_compatibility_matrix_job(
    payload: CompatibilityJobRequest,
    db: AsyncSession = Depends(get_db),
) -> CompatibilityJobResponse:
    """
    Menjadwalkan Tahap 5 di background worker dan langsung membalas 202 dengan
    `jobId`. Ini jalur yang dipakai tombol "make digitaltwin": jumlah panggilan
    agent tumbuh sebagai (worker x job desk), sehingga menjalankannya di dalam
    request HTTP akan kena timeout reverse proxy pada pabrik berukuran wajar.
    Pantau progresnya lewat `GET /documents/step-5/jobs/{job_id}`.
    """
    dt_service = DigitalTwinService(db)
    if await dt_service.get_factory(payload.factory_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factory '{payload.factory_id}' tidak ditemukan.",
        )
    job = await worker_tasks.enqueue_compatibility_matrix(
        factory_id=payload.factory_id,
        max_workers=payload.max_workers,
        max_attempts=payload.max_attempts,
        strict_compatibility=payload.strict_compatibility,
        persist=payload.persist,
    )
    return CompatibilityJobResponse.from_job(job)

@router.get(
    "/step-5/jobs",
    response_model=list[CompatibilityJobResponse],
    response_model_by_alias=True,
    summary="Daftar job matriks kompatibilitas (opsional difilter per factory)",
)
async def list_compatibility_matrix_jobs(
    factory_id: str | None = Query(None, description="Filter berdasarkan factory_id"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[CompatibilityJobResponse]:
    jobs = await worker_tasks.list_jobs(factory_id=factory_id, limit=limit, offset=offset)
    return [CompatibilityJobResponse.from_job(job) for job in jobs]

@router.get(
    "/step-5/jobs/{job_id}",
    response_model=CompatibilityJobResponse,
    response_model_by_alias=True,
    summary="Polling status & progres satu job matriks kompatibilitas",
)
async def get_compatibility_matrix_job(
    job_id: str = Path(..., description="ID job hasil POST /documents/step-5/jobs"),
) -> CompatibilityJobResponse:
    job = await worker_tasks.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job matriks kompatibilitas '{job_id}' tidak ditemukan.",
        )
    return CompatibilityJobResponse.from_job(job)

@router.delete(
    "/step-5/jobs/{job_id}",
    response_model=CompatibilityJobResponse,
    response_model_by_alias=True,
    summary="Batalkan job matriks kompatibilitas yang masih berjalan",
)
async def cancel_compatibility_matrix_job(
    job_id: str = Path(..., description="ID job hasil POST /documents/step-5/jobs"),
) -> CompatibilityJobResponse:
    job = await worker_tasks.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job matriks kompatibilitas '{job_id}' tidak ditemukan.",
        )
    if not await worker_tasks.cancel_job(job_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job '{job_id}' sudah berstatus '{job.status}' atau dijalankan "
                f"oleh proses backend lain, sehingga tidak bisa dibatalkan."
            ),
        )
    return CompatibilityJobResponse.from_job(await worker_tasks.get_job(job_id))


# --- Endpoint Audit Log & Status Job ---

@router.get(
    "/jobs/{job_id}",
    response_model=ParseJobResult,
    response_model_by_alias=True,
    summary="Ambil Detail Audit Log Parsing Job",
)
async def get_parse_job_detail(
    job_id: int = Path(..., description="ID Pekerjaan parsing dokumen (DocumentParseJob)"),
    db: AsyncSession = Depends(get_db),
) -> ParseJobResult:
    """Mendapatkan detail hasil audit trail pencatatan parsing job berdasarkan ID."""
    job = await db.get(service.DocumentParseJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parse job dengan ID '{job_id}' tidak ditemukan.",
        )
    return ParseJobResult.model_validate(job)

@router.get(
    "/factories",
    response_model=list[FactoryListItemResponse],
    response_model_by_alias=True,
    summary="Ambil Daftar Factory Terdaftar",
)
async def get_factory_list(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[FactoryListItemResponse]:
    """Mengambil daftar factory yang telah berhasil diparsing melalui service layer."""
    items = await service.get_parsed_factories_list(db, limit=limit, offset=offset)
    return [FactoryListItemResponse.model_validate(item) for item in items]