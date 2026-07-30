# app/modules/digital_twin_ingestion/repository.py
"""
Repository layer — satu-satunya tempat yang boleh menyusun query SQLAlchemy
untuk domain digital_twin_ingestion. Service layer (service.py) memanggil
fungsi-fungsi di sini dan tidak pernah menyentuh `select()`/session langsung.

Semua fungsi menerima `AsyncSession` eksplisit sebagai argumen pertama
(mengikuti pola `db` yang sudah dipakai di service.py stub) dan TIDAK
melakukan commit sendiri kecuali disebutkan (`create_*`, `save_*`) —
supaya service layer bebas menggabungkan beberapa operasi dalam satu
transaksi kalau perlu.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.digital_twin_ingestion import exceptions, models, schemas


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 1. IngestionJob — create / read / status transitions

async def create_job(
    db: AsyncSession,
    *,
    factory_id: str,
    requested_by: str,
    source_files: Sequence[schemas.SourceFileMeta],
) -> models.IngestionJob:
    job = models.IngestionJob(
        job_id=uuid.uuid4(),
        factory_id=factory_id,
        requested_by=requested_by,
        status=schemas.IngestionStatus.queued,
        source_files=[f.model_dump(mode="json") for f in source_files],
    )
    db.add(job)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> models.IngestionJob | None:
    return await db.get(models.IngestionJob, job_id)


async def get_job_or_raise(db: AsyncSession, job_id: uuid.UUID) -> models.IngestionJob:
    job = await get_job(db, job_id)
    if job is None:
        raise exceptions.IngestionJobNotFoundError(job_id)
    return job


async def list_jobs_by_factory(
    db: AsyncSession,
    factory_id: str,
    *,
    status: schemas.IngestionStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[models.IngestionJob]:
    stmt = (
        select(models.IngestionJob)
        .where(models.IngestionJob.factory_id == factory_id)
        .order_by(models.IngestionJob.submitted_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(models.IngestionJob.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_job_status(
    db: AsyncSession,
    job_id: uuid.UUID,
    new_status: schemas.IngestionStatus,
    *,
    error_message: str | None = None,
) -> models.IngestionJob:
    job = await get_job_or_raise(db, job_id)

    if job.status == schemas.IngestionStatus.failed and new_status != schemas.IngestionStatus.failed:
        raise exceptions.IngestionJobFailedError(job_id, job.error_message)

    job.status = new_status
    job.error_message = error_message

    if new_status == schemas.IngestionStatus.parsing_tables and job.started_at is None:
        job.started_at = _utcnow()
    if new_status in (
        schemas.IngestionStatus.committed,
        schemas.IngestionStatus.failed,
        schemas.IngestionStatus.cancelled,
    ):
        job.finished_at = _utcnow()

    await db.flush()
    return job


async def update_cv_progress(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    total_cv: int | None = None,
    processed_delta: int = 0,
    failed_delta: int = 0,
) -> models.IngestionJob:
    job = await get_job_or_raise(db, job_id)
    if total_cv is not None:
        job.cv_total = total_cv
    job.cv_processed += processed_delta
    job.cv_failed += failed_delta
    await db.flush()
    return job


async def cancel_job(db: AsyncSession, job_id: uuid.UUID) -> models.IngestionJob:
    job = await get_job_or_raise(db, job_id)
    if job.status in (
        schemas.IngestionStatus.committed,
        schemas.IngestionStatus.failed,
        schemas.IngestionStatus.cancelled,
    ):
        raise exceptions.IngestionJobNotCancellableError(job_id, job.status.value)
    job.status = schemas.IngestionStatus.cancelled
    job.finished_at = _utcnow()
    await db.flush()
    return job


# 2. CV extraction & ambiguity records

async def bulk_save_cv_extractions(
    db: AsyncSession,
    job_id: uuid.UUID,
    extractions: Sequence[schemas.CVExtractionResult],
) -> list[models.CVExtractionRecord]:
    records = [
        models.CVExtractionRecord(
            job_id=job_id,
            cv_filename=e.cv_filename,
            extracted_name=e.extracted_name,
            extracted_age=e.extracted_age,
            extracted_years_of_experience=e.extracted_years_of_experience,
            extracted_skills=list(e.extracted_skills),
            extracted_education=list(e.extracted_education),
            raw_llm_notes=e.raw_llm_notes,
        )
        for e in extractions
    ]
    db.add_all(records)
    await db.flush()
    return records


async def list_cv_extractions(
    db: AsyncSession, job_id: uuid.UUID
) -> Sequence[models.CVExtractionRecord]:
    stmt = select(models.CVExtractionRecord).where(models.CVExtractionRecord.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def set_cv_match(
    db: AsyncSession,
    job_id: uuid.UUID,
    cv_filename: str,
    *,
    matched_worker_id: str | None,
    match_confidence: schemas.ConfidenceLevel | None,
) -> models.CVExtractionRecord:
    stmt = select(models.CVExtractionRecord).where(
        models.CVExtractionRecord.job_id == job_id,
        models.CVExtractionRecord.cv_filename == cv_filename,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise exceptions.PatchTargetNotFoundError("CVExtractionRecord", cv_filename)
    record.matched_worker_id = matched_worker_id
    record.match_confidence = match_confidence
    await db.flush()
    return record


async def bulk_save_ambiguities(
    db: AsyncSession,
    job_id: uuid.UUID,
    ambiguities: Sequence[schemas.CVMatchAmbiguity],
) -> list[models.CVMatchAmbiguityRecord]:
    records = [
        models.CVMatchAmbiguityRecord(
            job_id=job_id,
            cv_filename=a.cv_filename,
            extracted_name=a.extracted_name,
            candidate_worker_ids=list(a.candidate_worker_ids),
            similarity_scores=list(a.similarity_scores),
            reason=a.reason,
        )
        for a in ambiguities
    ]
    db.add_all(records)
    await db.flush()
    return records


async def list_ambiguities(
    db: AsyncSession, job_id: uuid.UUID, *, unresolved_only: bool = False
) -> Sequence[models.CVMatchAmbiguityRecord]:
    stmt = select(models.CVMatchAmbiguityRecord).where(
        models.CVMatchAmbiguityRecord.job_id == job_id
    )
    if unresolved_only:
        stmt = stmt.where(models.CVMatchAmbiguityRecord.resolved.is_(False))
    result = await db.execute(stmt)
    return result.scalars().all()


async def resolve_ambiguity(
    db: AsyncSession, job_id: uuid.UUID, cv_filename: str
) -> models.CVMatchAmbiguityRecord:
    stmt = select(models.CVMatchAmbiguityRecord).where(
        models.CVMatchAmbiguityRecord.job_id == job_id,
        models.CVMatchAmbiguityRecord.cv_filename == cv_filename,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise exceptions.PatchTargetNotFoundError("CVMatchAmbiguityRecord", cv_filename)
    record.resolved = True
    record.resolved_at = _utcnow()
    await db.flush()
    return record


# 3. Draft — upsert / read / patch

async def upsert_draft(
    db: AsyncSession, job_id: uuid.UUID, factory_id: str, draft: schemas.DigitalTwinDraft
) -> models.DigitalTwinDraftRecord:
    record = await db.get(models.DigitalTwinDraftRecord, job_id)
    payload = dict(
        factory_id=factory_id,
        factory_info=draft.factory_info.model_dump(mode="json"),
        assets=[a.model_dump(mode="json") for a in draft.assets],
        job_descriptions=[j.model_dump(mode="json") for j in draft.job_descriptions],
        workers=[w.model_dump(mode="json") for w in draft.workers],
        llm_compatibility_and_evaluations=[
            c.model_dump(mode="json") for c in draft.llm_compatibility_and_evaluations
        ],
        unmatched_cvs=[c.model_dump(mode="json") for c in draft.unmatched_cvs],
        ambiguous_matches=[a.model_dump(mode="json") for a in draft.ambiguous_matches],
        review_required=draft.review_required,
        generated_at=draft.generated_at,
    )
    if record is None:
        record = models.DigitalTwinDraftRecord(job_id=job_id, **payload)
        db.add(record)
    else:
        for field, value in payload.items():
            setattr(record, field, value)
    await db.flush()
    return record


async def get_draft(db: AsyncSession, job_id: uuid.UUID) -> models.DigitalTwinDraftRecord | None:
    return await db.get(models.DigitalTwinDraftRecord, job_id)


async def get_draft_or_raise(
    db: AsyncSession, job_id: uuid.UUID
) -> models.DigitalTwinDraftRecord:
    draft = await get_draft(db, job_id)
    if draft is None:
        raise exceptions.DraftNotFoundError(job_id)
    return draft


async def replace_draft_worker(
    db: AsyncSession, job_id: uuid.UUID, worker_id: str, updated_worker: dict
) -> models.DigitalTwinDraftRecord:
    """Ganti satu entry di `workers` (list JSON) berdasarkan worker_id — dipakai
    oleh operasi set_field / reassign_cv / unassign_cv saat patch_draft."""
    draft = await get_draft_or_raise(db, job_id)
    workers = list(draft.workers)
    for idx, w in enumerate(workers):
        if w.get("worker_id") == worker_id:
            workers[idx] = updated_worker
            break
    else:
        raise exceptions.WorkerNotFoundInDraftError(worker_id)
    draft.workers = workers
    await db.flush()
    return draft


async def remove_draft_worker(
    db: AsyncSession, job_id: uuid.UUID, worker_id: str
) -> models.DigitalTwinDraftRecord:
    draft = await get_draft_or_raise(db, job_id)
    workers = [w for w in draft.workers if w.get("worker_id") != worker_id]
    if len(workers) == len(draft.workers):
        raise exceptions.WorkerNotFoundInDraftError(worker_id)
    draft.workers = workers
    # Buang juga compatibility entries yang mereferensikan worker ini supaya draft konsisten
    draft.llm_compatibility_and_evaluations = [
        c
        for c in draft.llm_compatibility_and_evaluations
        if c.get("worker_id") != worker_id
    ]
    await db.flush()
    return draft


async def recompute_review_required(
    db: AsyncSession, job_id: uuid.UUID
) -> models.DigitalTwinDraftRecord:
    """Set `review_required` berdasarkan sisa unmatched_cvs / ambiguous_matches
    yang belum di-resolve. Dipanggil setelah setiap operasi patch."""
    draft = await get_draft_or_raise(db, job_id)
    unresolved_ambiguities = await list_ambiguities(db, job_id, unresolved_only=True)
    draft.review_required = bool(draft.unmatched_cvs) or bool(unresolved_ambiguities)
    await db.flush()
    return draft


# 4. Commit — finalize, immutable setelahnya

async def save_commit(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    factory_id: str,
    committed_by: str,
    digital_twin: schemas.DigitalTwin,
) -> models.DigitalTwinCommitRecord:
    existing = await db.get(models.DigitalTwinCommitRecord, job_id)
    if existing is not None:
        raise exceptions.DigitalTwinAlreadyCommittedError(job_id)

    record = models.DigitalTwinCommitRecord(
        job_id=job_id,
        factory_id=factory_id,
        committed_by=committed_by,
        digital_twin=digital_twin.model_dump(mode="json"),
    )
    db.add(record)
    await db.flush()
    return record


async def get_commit(db: AsyncSession, job_id: uuid.UUID) -> models.DigitalTwinCommitRecord | None:
    return await db.get(models.DigitalTwinCommitRecord, job_id)


async def get_latest_commit_for_factory(
    db: AsyncSession, factory_id: str
) -> models.DigitalTwinCommitRecord | None:
    stmt = (
        select(models.DigitalTwinCommitRecord)
        .where(models.DigitalTwinCommitRecord.factory_id == factory_id)
        .order_by(models.DigitalTwinCommitRecord.committed_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# 5. Convenience — job dengan seluruh relasi ter-eager-load, untuk endpoint detail

async def get_job_with_relations(
    db: AsyncSession, job_id: uuid.UUID
) -> models.IngestionJob:
    stmt = (
        select(models.IngestionJob)
        .where(models.IngestionJob.job_id == job_id)
        .options(
            selectinload(models.IngestionJob.cv_extractions),
            selectinload(models.IngestionJob.ambiguous_matches),
            selectinload(models.IngestionJob.draft),
            selectinload(models.IngestionJob.commit),
        )
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        raise exceptions.IngestionJobNotFoundError(job_id)
    return job