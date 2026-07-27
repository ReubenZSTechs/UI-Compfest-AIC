# app/api/v1/endpoints/digital_twin_ingestion.py
"""
Endpoint untuk ingest raw input (3 tabel + folder CV) menjadi Digital Twin JSON.

Pipeline: upload -> parse tabel -> extract CV (LLM) -> merge -> sintesis (LLM) -> draft -> commit
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from app.api.deps import get_db, get_current_user
from app.modules.digital_twin_ingestion import schemas, service

router = APIRouter()


# Upload & mulai proses ingestion

@router.post(
    "/ingest",
    response_model=schemas.IngestionJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload 3 tabel + folder CV, mulai proses generate Digital Twin",
)
async def start_ingestion(
    factory_id: str,
    process_table: UploadFile = File(..., description="Tabel penjelasan proses pabrik (urutan workflow & mesin per step)"),
    jobdesk_table: UploadFile = File(..., description="Tabel jobdesk tiap karyawan/posisi"),
    asset_table: UploadFile = File(..., description="Tabel jumlah & kapasitas alat/mesin"),
    cv_files: list[UploadFile] = File(..., description="Kumpulan file CV karyawan (PDF/DOCX), satu file per orang"),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Tidak diproses secara blocking — file disimpan, lalu job di-enqueue
    ke background worker karena parsing CV via LLM butuh waktu (1 call per CV).
    """
    job = await service.enqueue_ingestion_job(
        db,
        factory_id=factory_id,
        process_table=process_table,
        jobdesk_table=jobdesk_table,
        asset_table=asset_table,
        cv_files=cv_files,
        requested_by=current_user.id,
    )
    return job


# Cek status & progress

@router.get(
    "/ingest/{job_id}",
    response_model=schemas.IngestionJobStatus,
    summary="Cek status & progress ingestion (mis. n/total CV sudah diproses)",
)
async def get_ingestion_status(
    job_id: UUID,
    db=Depends(get_db),
):
    """
    Status: queued -> parsing_tables -> parsing_cvs (progress n/total)
            -> merging -> synthesizing -> ready_for_review / failed
    """
    job = await service.get_ingestion_status(db, job_id=job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Ingestion job '{job_id}' tidak ditemukan.")
    return job


# Review hasil draft sebelum di-commit jadi Digital Twin resmi

@router.get(
    "/ingest/{job_id}/draft",
    response_model=schemas.DigitalTwinDraft,
    summary="Ambil draft Digital Twin hasil parsing (belum resmi/committed)",
)
async def get_ingestion_draft(
    job_id: UUID,
    db=Depends(get_db),
):
    """
    Draft berisi assets, job_desks, workers (hasil merge tabel + CV),
    beserta flag confidence/ambiguity yang perlu direview manusia
    (mis. CV tidak match nama karyawan di tabel jobdesk).
    """
    draft = await service.get_draft(db, job_id=job_id)
    if draft is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Draft untuk job '{job_id}' belum tersedia (job mungkin belum selesai).",
        )
    return draft


@router.patch(
    "/ingest/{job_id}/draft",
    response_model=schemas.DigitalTwinDraft,
    summary="Edit manual draft sebelum commit (mis. perbaiki mapping CV yang salah)",
)
async def patch_ingestion_draft(
    job_id: UUID,
    patch: schemas.DigitalTwinDraftPatch,
    db=Depends(get_db),
):
    """Untuk human-in-the-loop correction sebelum data jadi resmi."""
    updated = await service.patch_draft(db, job_id=job_id, patch=patch)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Draft '{job_id}' tidak ditemukan.")
    return updated


# Commit — jadikan Digital Twin resmi (dipakai RL engine)

@router.post(
    "/ingest/{job_id}/commit",
    response_model=schemas.DigitalTwinCommitResponse,
    summary="Finalisasi draft menjadi Digital Twin resmi",
)
async def commit_ingestion(
    job_id: UUID,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Menyimpan draft sebagai Digital Twin resmi (factory_workflow_digital_twin.json
    setara di DB), lalu men-trigger generate llm_compatibility_and_evaluations
    penuh jika belum dilakukan di tahap sintesis.
    """
    result = await service.commit_draft(db, job_id=job_id, committed_by=current_user.id)
    if result is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Draft tidak dalam status 'ready_for_review' atau sudah di-commit.",
        )
    return result


@router.delete(
    "/ingest/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Batalkan job ingestion (hapus draft & file sementara)",
)
async def cancel_ingestion(
    job_id: UUID,
    db=Depends(get_db),
):
    await service.cancel_ingestion(db, job_id=job_id)