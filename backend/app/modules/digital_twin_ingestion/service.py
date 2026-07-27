# app/modules/digital_twin_ingestion/service.py
"""STUB — implementasi penuh (parsing tabel, LLM CV extraction, fuzzy matching) menyusul."""

from uuid import UUID

from fastapi import UploadFile

from app.modules.digital_twin_ingestion import schemas


async def enqueue_ingestion_job(
    db, factory_id: str, process_table: UploadFile, jobdesk_table: UploadFile,
    asset_table: UploadFile, cv_files: list[UploadFile], requested_by: str,
) -> schemas.IngestionJobAccepted:
    raise NotImplementedError


async def get_ingestion_status(db, job_id: UUID) -> schemas.IngestionJobStatus | None:
    raise NotImplementedError


async def get_draft(db, job_id: UUID) -> schemas.DigitalTwinDraft | None:
    raise NotImplementedError


async def patch_draft(db, job_id: UUID, patch: schemas.DigitalTwinDraftPatch) -> schemas.DigitalTwinDraft | None:
    raise NotImplementedError


async def commit_draft(db, job_id: UUID, committed_by: str) -> schemas.DigitalTwinCommitResponse | None:
    raise NotImplementedError


async def cancel_ingestion(db, job_id: UUID) -> None:
    raise NotImplementedError
