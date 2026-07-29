# app/modules/digital_twin_ingestion/schemas.py
"""
Pydantic schemas untuk domain Digital Twin Ingestion.

Pipeline yang dimodelkan:
    upload (3 tabel + folder CV)
        -> parsing_tables
        -> parsing_cvs        (LLM extraction per file CV)
        -> merging            (cocokkan CV ke worker by nama)
        -> synthesizing       (LLM generate compatibility matrix & reasoning)
        -> ready_for_review   (draft, human-in-the-loop koreksi)
        -> committed          (jadi DigitalTwin resmi, dipakai RL engine)

Reuse model dari app.modules.rl_optimization.schemas (Asset, JobDesk, Worker,
FactoryInfo, CompatibilityEntry, DigitalTwin) supaya tidak ada duplikasi
struktur inti — modul ini hanya menambah lapisan "draft metadata"
(confidence, provenance, ambiguity) di atasnya.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.rl_optimization.schemas import (
    Asset,
    CompatibilityEntry,
    DigitalTwin,
    FactoryInfo,
    JobDesk,
    Worker,
    WorkerDemographics,
)


# Enums

class IngestionStatus(str, Enum):
    queued = "queued"
    parsing_tables = "parsing_tables"
    parsing_cvs = "parsing_cvs"
    merging = "merging"
    synthesizing = "synthesizing"
    ready_for_review = "ready_for_review"
    committed = "committed"
    failed = "failed"
    cancelled = "cancelled"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class DataSource(str, Enum):
    """Asal satu nilai/record di draft — penting untuk audit & review."""

    table_process = "table_process"       # tabel penjelasan proses pabrik
    table_jobdesk = "table_jobdesk"        # tabel jobdesk karyawan
    table_asset = "table_asset"            # tabel jumlah alat
    cv_extraction = "cv_extraction"        # hasil LLM extract dari CV
    llm_inferred = "llm_inferred"          # LLM mengisi gap tanpa sumber eksplisit
    manual_edit = "manual_edit"            # hasil PATCH oleh user saat review


class PatchOperation(str, Enum):
    set_field = "set_field"
    reassign_cv = "reassign_cv"
    unassign_cv = "unassign_cv"
    remove_worker = "remove_worker"
    remove_ambiguity_flag = "remove_ambiguity_flag"


# 1. Upload & Job Status

class SourceFileMeta(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class IngestionJobAccepted(BaseModel):
    job_id: UUID
    factory_id: str
    status: IngestionStatus = IngestionStatus.queued
    submitted_at: datetime
    source_files: list[SourceFileMeta] = Field(
        ..., description="Ringkasan 3 file tabel + N file CV yang diterima"
    )


class CVParsingProgress(BaseModel):
    total_cv: int
    processed_cv: int = 0
    failed_cv: int = 0

    @property
    def progress_pct(self) -> float:
        if self.total_cv == 0:
            return 0.0
        return round((self.processed_cv / self.total_cv) * 100, 1)


class IngestionJobStatus(BaseModel):
    job_id: UUID
    factory_id: str
    status: IngestionStatus
    cv_progress: Optional[CVParsingProgress] = Field(
        None, description="Hanya terisi saat status = parsing_cvs"
    )
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# 2. Draft — hasil merge tabel + CV, sebelum di-commit

class ProvenancedField(BaseModel):
    """
    Wrapper generik untuk nilai yang perlu dilacak asalnya, mis. usia
    worker bisa datang dari tabel ATAU dari CV (kalau tidak ada di tabel).
    """

    value: Optional[str] = None
    source: DataSource
    confidence: ConfidenceLevel = ConfidenceLevel.high


class CVExtractionResult(BaseModel):
    """Hasil mentah LLM extraction dari satu file CV, sebelum dicocokkan ke worker."""

    cv_filename: str
    extracted_name: Optional[str] = None
    extracted_age: Optional[int] = None
    extracted_years_of_experience: Optional[float] = None
    extracted_skills: list[str] = Field(default_factory=list)
    extracted_education: list[str] = Field(default_factory=list)
    raw_llm_notes: Optional[str] = Field(
        None, description="Catatan bebas LLM, mis. bagian CV yang ambigu/tidak terbaca"
    )


class CVMatchAmbiguity(BaseModel):
    """
    Ditandai saat proses merging tidak bisa mencocokkan CV ke worker
    dengan confidence tinggi (mis. nama beda ejaan, atau 1 CV cocok
    dengan >1 worker).
    """

    cv_filename: str
    extracted_name: Optional[str] = None
    candidate_worker_ids: list[str] = Field(
        ..., description="Worker_id yang menjadi kandidat match, diurutkan dari paling mirip"
    )
    similarity_scores: list[float] = Field(
        default_factory=list, description="Skor kemiripan nama, sejajar index dengan candidate_worker_ids"
    )
    reason: str


class DraftWorker(Worker):
    """Worker versi draft — field demographics bisa parsial + ada provenance."""

    matched_cv_filename: Optional[str] = None
    match_confidence: Optional[ConfidenceLevel] = None
    demographics_source: dict[str, DataSource] = Field(
        default_factory=dict,
        description="Mapping nama field -> asal data, mis. {'age': 'cv_extraction', 'years_of_experience': 'table_jobdesk'}",
    )
    needs_review: bool = False


class DraftAsset(Asset):
    source: DataSource = DataSource.table_asset
    needs_review: bool = False


class DraftJobDesk(JobDesk):
    source: DataSource = DataSource.table_jobdesk
    needs_review: bool = False


class DigitalTwinDraft(BaseModel):
    job_id: UUID
    factory_id: str
    status: IngestionStatus
    factory_info: FactoryInfo
    assets: list[DraftAsset]
    job_descriptions: list[DraftJobDesk]
    workers: list[DraftWorker]
    llm_compatibility_and_evaluations: list[CompatibilityEntry] = Field(
        default_factory=list,
        description="Kosong jika tahap 'synthesizing' belum selesai",
    )
    unmatched_cvs: list[CVExtractionResult] = Field(
        default_factory=list,
        description="CV yang berhasil diekstrak tapi tidak ditemukan worker cocok di tabel jobdesk",
    )
    ambiguous_matches: list[CVMatchAmbiguity] = Field(
        default_factory=list,
        description="CV yang cocok ke >1 worker atau confidence rendah — wajib direview manusia",
    )
    review_required: bool = Field(
        ..., description="True jika ada unmatched_cvs atau ambiguous_matches yang belum diselesaikan"
    )
    generated_at: datetime


# 3. Patch — koreksi manual sebelum commit (human-in-the-loop)

class SetFieldPatch(BaseModel):
    operation: PatchOperation = PatchOperation.set_field
    target_worker_id: str
    field_path: str = Field(
        ..., description="Dot path ke field, mis. 'demographics.age' atau 'demographics.years_of_experience'"
    )
    new_value: str


class ReassignCVPatch(BaseModel):
    operation: PatchOperation = PatchOperation.reassign_cv
    cv_filename: str
    target_worker_id: str = Field(
        ..., description="Worker_id yang benar untuk CV ini (mis. hasil resolusi dari ambiguous_matches)"
    )


class UnassignCVPatch(BaseModel):
    operation: PatchOperation = PatchOperation.unassign_cv
    worker_id: str
    reason: Optional[str] = None


class RemoveWorkerPatch(BaseModel):
    operation: PatchOperation = PatchOperation.remove_worker
    worker_id: str
    reason: Optional[str] = None


class RemoveAmbiguityFlagPatch(BaseModel):
    """Dipakai saat user menyatakan satu ambiguous_match tidak relevan (mis. CV memang tidak ada worker-nya)."""

    operation: PatchOperation = PatchOperation.remove_ambiguity_flag
    cv_filename: str


class DigitalTwinDraftPatch(BaseModel):
    """
    Kumpulan operasi koreksi yang diterapkan sekaligus dalam satu request.
    Diproses berurutan sesuai urutan list oleh service layer.
    """

    set_field_ops: list[SetFieldPatch] = Field(default_factory=list)
    reassign_cv_ops: list[ReassignCVPatch] = Field(default_factory=list)
    unassign_cv_ops: list[UnassignCVPatch] = Field(default_factory=list)
    remove_worker_ops: list[RemoveWorkerPatch] = Field(default_factory=list)
    remove_ambiguity_flag_ops: list[RemoveAmbiguityFlagPatch] = Field(default_factory=list)


# 4. Commit — finalisasi draft jadi Digital Twin resmi

class DigitalTwinCommitResponse(BaseModel):
    job_id: UUID
    factory_id: str
    committed_at: datetime
    committed_by: str
    digital_twin: DigitalTwin = Field(
        ..., description="Bentuk final, setara response dari GET /rl/digital-twin"
    )
