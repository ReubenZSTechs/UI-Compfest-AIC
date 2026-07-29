# app/modules/digital_twin_ingestion/models.py
"""
SQLAlchemy models untuk domain Digital Twin Ingestion.

Catatan desain:
- Satu `IngestionJob` merepresentasikan satu pipeline run: upload -> ... -> committed.
- Payload yang secara alami "dokumen" (list asset, list job_descriptions, list workers,
  compatibility matrix, dsb.) disimpan sebagai JSON/JSONB alih-alih dinormalisasi
  penuh ke banyak tabel, karena:
    1. Bentuknya persis mengikuti Pydantic schema di schemas.py (DigitalTwinDraft,
       DraftWorker, dst.) sehingga round-trip model <-> schema jadi sederhana.
    2. Selama status masih `ready_for_review`, data ini masih draft & bisa berubah
       bentuk (field baru dari LLM, dsb.) — JSON lebih toleran terhadap itu
       dibanding kolom relasional yang kaku.
  Entity yang butuh query granular (CV extraction per file, ambiguity per CV)
  tetap dinormalisasi sebagai baris terpisah supaya bisa di-filter/di-update
  satu-satu saat human-in-the-loop review.
- Enum Python di schemas.py (IngestionStatus, DataSource, ConfidenceLevel,
  PatchOperation) dipakai ulang sebagai SQLAlchemy Enum agar satu source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.digital_twin_ingestion.schemas import (
    ConfidenceLevel,
    DataSource,
    IngestionStatus,
)

# Pakai JSONB kalau backend Postgres, fallback ke JSON generik untuk dialect lain
# (mis. SQLite di test suite). SQLAlchemy akan otomatis pilih implementasi yang
# tepat berdasarkan dialect saat runtime kalau kita pakai `.with_variant`.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        primary_key=True,
        default=uuid.uuid4,
    )


# 1. IngestionJob — root aggregate dari satu pipeline run

class IngestionJob(Base):
    __tablename__ = "digital_twin_ingestion_jobs"

    job_id: Mapped[uuid.UUID] = _uuid_pk()
    factory_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, name="ingestion_status"),
        default=IngestionStatus.queued,
        nullable=False,
        index=True,
    )

    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)

    # Ringkasan file yang di-upload (nama, content_type, size, dst.), disimpan
    # sebagai JSON list — cocok 1:1 dengan schemas.SourceFileMeta.
    source_files: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)

    # Progress khusus tahap parsing_cvs (schemas.CVParsingProgress)
    cv_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cv_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cv_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    cv_extractions: Mapped[list["CVExtractionRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    ambiguous_matches: Mapped[list["CVMatchAmbiguityRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    draft: Mapped["DigitalTwinDraftRecord | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    commit: Mapped["DigitalTwinCommitRecord | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IngestionJob {self.job_id} status={self.status}>"


# 2. CV extraction & matching — dinormalisasi supaya bisa di-review per baris

class CVExtractionRecord(Base):
    """Hasil mentah LLM extraction dari satu file CV (schemas.CVExtractionResult)."""

    __tablename__ = "digital_twin_ingestion_cv_extractions"
    __table_args__ = (
        UniqueConstraint("job_id", "cv_filename", name="uq_cv_extraction_job_filename"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("digital_twin_ingestion_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cv_filename: Mapped[str] = mapped_column(String(256), nullable=False)
    extracted_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    extracted_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_years_of_experience: Mapped[float | None] = mapped_column(nullable=True)
    extracted_skills: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    extracted_education: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    raw_llm_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hasil merging — None selama belum berhasil dicocokkan ke worker manapun
    matched_worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    match_confidence: Mapped[ConfidenceLevel | None] = mapped_column(
        SAEnum(ConfidenceLevel, name="confidence_level"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["IngestionJob"] = relationship(back_populates="cv_extractions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CVExtractionRecord {self.cv_filename} job={self.job_id}>"


class CVMatchAmbiguityRecord(Base):
    """CV yang tidak bisa di-merge dengan confidence tinggi (schemas.CVMatchAmbiguity)."""

    __tablename__ = "digital_twin_ingestion_cv_ambiguities"
    __table_args__ = (
        UniqueConstraint("job_id", "cv_filename", name="uq_cv_ambiguity_job_filename"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("digital_twin_ingestion_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    cv_filename: Mapped[str] = mapped_column(String(256), nullable=False)
    extracted_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    candidate_worker_ids: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    similarity_scores: Mapped[list[float]] = mapped_column(JSONType, default=list, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    # Ditandai True saat user resolve via ReassignCVPatch/RemoveAmbiguityFlagPatch
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["IngestionJob"] = relationship(back_populates="ambiguous_matches")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CVMatchAmbiguityRecord {self.cv_filename} resolved={self.resolved}>"


# 3. Draft — snapshot DigitalTwinDraft, satu-ke-satu dengan job

class DigitalTwinDraftRecord(Base):
    """
    Persist bentuk penuh schemas.DigitalTwinDraft.

    assets / job_descriptions / workers / llm_compatibility_and_evaluations disimpan
    sebagai JSON list-of-dict yang match langsung dengan DraftAsset / DraftJobDesk
    / DraftWorker / CompatibilityEntry — di-serialize/deserialize di repository
    layer, bukan di sini, supaya model tetap tipis dan bebas dari dependency
    Pydantic saat query-only.
    """

    __tablename__ = "digital_twin_ingestion_drafts"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("digital_twin_ingestion_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    )
    factory_id: Mapped[str] = mapped_column(String(64), nullable=False)

    factory_info: Mapped[dict] = mapped_column(JSONType, nullable=False)
    assets: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)
    job_descriptions: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)
    workers: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)
    llm_compatibility_and_evaluations: Mapped[list[dict]] = mapped_column(
        JSONType, default=list, nullable=False
    )
    unmatched_cvs: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)
    ambiguous_matches: Mapped[list[dict]] = mapped_column(JSONType, default=list, nullable=False)

    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    job: Mapped["IngestionJob"] = relationship(back_populates="draft")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DigitalTwinDraftRecord job={self.job_id} review_required={self.review_required}>"


# 4. Commit — snapshot final DigitalTwin resmi, immutable setelah dibuat

class DigitalTwinCommitRecord(Base):
    """Persist schemas.DigitalTwinCommitResponse. Satu job hanya boleh commit sekali."""

    __tablename__ = "digital_twin_ingestion_commits"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True).with_variant(String(36), "sqlite"),
        ForeignKey("digital_twin_ingestion_jobs.job_id", ondelete="CASCADE"),
        primary_key=True,
    )
    factory_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    committed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Bentuk final schemas.DigitalTwin, disimpan utuh sebagai JSON supaya
    # GET /rl/digital-twin bisa langsung serve tanpa rekonstruksi dari draft.
    digital_twin: Mapped[dict] = mapped_column(JSONType, nullable=False)

    job: Mapped["IngestionJob"] = relationship(back_populates="commit")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DigitalTwinCommitRecord job={self.job_id} factory={self.factory_id}>"