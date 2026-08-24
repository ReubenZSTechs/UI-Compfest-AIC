"""
backend/app/modules/documents/schemas.py

Skema data modul documents (Pipeline Terpadu, Kombinasi Tahap 1-5, & Tahap 3 s/d 5).
Sesuai dengan Standar Kontrak Data Digital Twin System.

Perubahan pada revisi ini:
1. DITAMBAHKAN: skema request/response untuk alur MANUAL (form-based) yang menggantikan
   parsing PDF/ZIP otomatis -- lihat blok "SKEMA INPUT MANUAL" di bagian bawah file.
   Skema ini dipetakan langsung dari `spesifikasi-flowchart-form-manual.md`
   (Tahap 1 s/d Tahap 8), sehingga field & validasinya konsisten dengan anatomi
   node flowchart yang sudah disepakati.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class BaseDocumentSchema(BaseModel):
    """Base schema dengan alias camelCase otomatis dan dukungan ORM conversion."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


@dataclass
class PipelineResult:
    """Dataclass internal untuk transfer data antar service dan repository."""

    factory_structure: dict[str, Any]
    worker_profile: dict[str, Any]
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]]
    floor_state: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


# --- Ringkasan Ekstraksi & Response Terpadu (Tahap 1+2) ---

class ExtractionSummary(BaseDocumentSchema):
    extracted_fields: dict[str, str] = Field(default_factory=dict)
    tables_count: int = 0
    raw_text: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProcessFactoryDocumentResponse(BaseDocumentSchema):
    parse_job_id: str | None = None
    agent_input: str
    factory_structure: dict[str, Any]
    extraction_summary: ExtractionSummary


# --- Skema Endpoint Individual (Tahap 3 s/d 5) ---

class Step3Request(BaseDocumentSchema):
    factory_structure: dict[str, Any]


class Step3Response(BaseDocumentSchema):
    is_valid: bool
    blocking_gaps: list[str] = Field(default_factory=list)
    warning_gaps: list[str] = Field(default_factory=list)


# --- Skema Tahap 4 (ZIP & Profil Pekerja) ---

class ArchiveReportSummary(BaseDocumentSchema):
    archive_name: str
    accepted_count: int = 0
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    failed: list[dict[str, Any]] = Field(default_factory=list)


class Step4Response(BaseDocumentSchema):
    factory_id: str | None = None
    worker_profile: dict[str, Any]
    worker_agent_input: str
    candidates_found: int = 0
    rejected_blocks_count: int = 0
    workers_persisted: int = 0
    archive_reports: list[ArchiveReportSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- Skema Kombinasi (Tahap 1, 2, 4, & 5) -- ALUR OTOMATIS (PDF/ZIP) ---

class ProcessCombinedDocumentsResponse(BaseDocumentSchema):
    """
    Skema respon gabungan untuk pemrosesan dokumen pabrik (Tahap 1+2),
    ZIP CV pekerja (Tahap 4), dan matriks kompatibilitas (Tahap 5) sekaligus.
    """

    parse_job_id: str | None = None

    # Data Pabrik (Tahap 1 & 2)
    extraction_summary: ExtractionSummary
    agent_input: str
    factory_structure: dict[str, Any]

    # Data Worker (Tahap 4)
    worker_profile: dict[str, Any]
    worker_agent_input: str
    candidates_found: int = 0
    rejected_blocks_count: int = 0
    archive_reports: list[ArchiveReportSummary] = Field(default_factory=list)

    # Matriks Kompatibilitas (Tahap 5) - Mendukung objek dict maupun array flattened
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]]


# --- Skema Tahap 5 & Job Result ---

class Step5Request(BaseDocumentSchema):
    """
    Dua mode input yang saling menggantikan:
    1. `factoryId` saja -- struktur pabrik & profil pekerja dibaca dari Digital Twin DB
       (dipakai tombol "make digitaltwin" pada UI), hasilnya dipersist balik ke DB.
    2. `factoryStructure` + `workerProfile` -- mode stateless lama, tanpa akses DB.
    """

    factory_id: str | None = None
    factory_structure: dict[str, Any] | None = None
    worker_profile: dict[str, Any] | None = None
    max_workers: int = Field(default=4, ge=1, le=32)
    max_attempts: int = Field(default=3, ge=1, le=10)
    strict_compatibility: bool = False
    persist: bool = True

    @model_validator(mode="after")
    def require_input_source(self) -> "Step5Request":
        if not self.factory_id and not (self.factory_structure and self.worker_profile):
            raise ValueError(
                "Kirim 'factoryId', atau pasangan 'factoryStructure' + 'workerProfile'."
            )
        return self


class Step5Response(BaseDocumentSchema):
    factory_id: str | None = None
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]]
    pairs_evaluated: int = 0
    evaluations_persisted: int = 0
    failed_pairs: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParseJobResult(BaseDocumentSchema):
    job_id: str = Field(..., validation_alias="id")
    factory_id: str | None = None
    workers_parsed: int = 0
    job_desks_parsed: int = 0
    warnings: list[str] = Field(default_factory=list)
    factory_structure: dict[str, Any] | None = None
    worker_profile: dict[str, Any] | None = None
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]] | None = None
    floor_state: dict[str, Any] | None = None

    @field_validator("job_id", mode="before")
    @classmethod
    def coerce_job_id_to_str(cls, value: Any) -> str:
        """Mengonversi ID integer dari database/ORM menjadi string secara otomatis."""
        return str(value) if value is not None else ""


class FactoryListItemResponse(BaseModel):
    factory_id: str = Field(..., alias="factoryId")
    factory_name: str = Field(..., alias="factoryName")
    workers_count: int = Field(..., alias="workersCount")
    job_desks_count: int = Field(..., alias="jobDesksCount")
    created_at: Optional[str] = Field(None, alias="createdAt")
    job_id: Optional[str] = Field(None, alias="jobId")

    class Config:
        populate_by_name = True


# ==========================================================================
# SKEMA INPUT MANUAL (Form Frontend, Pengganti Parsing Otomatis PDF/ZIP)
# Dipetakan dari spesifikasi-flowchart-form-manual.md, Tahap 1 s/d Tahap 8.
# ==========================================================================

class CapacityMetricInput(BaseDocumentSchema):
    """Struktur bersama untuk capacity_per_unit / total_capacity / throughput."""

    value: float | None = None
    unit: str | None = None
    unit_class: str | None = None
    basis: str | None = None
    raw: str | None = None  # opsional; auto-dibangun dari value+unit bila kosong

    @field_validator("unit")
    @classmethod
    def value_unit_pair(cls, v, info):
        value = info.data.get("value")
        if (value is None) != (v is None):
            raise ValueError("value dan unit harus diisi bersamaan, atau dikosongkan bersamaan.")
        return v


class EnvironmentalFactorsInput(BaseDocumentSchema):
    power_consumption_watt: float | None = None
    noise_level_db: float | None = None
    vibration_hazard_level: Literal["low", "medium", "high"] = "low"
    physical_strain_index: float = Field(default=0.0, ge=0, le=1)


# --- Tahap 1: Factory (Info Dasar + Graph, digabung di sini untuk kemudahan payload) ---

class FactoryInfoManualInput(BaseDocumentSchema):
    factory_id: str
    factory_name: str
    process_type: str | None = None
    declared_worker_count: int | None = Field(default=None, ge=0)
    registered_worker_count: int | None = Field(default=None, ge=0)
    layout_description: str | None = None

    # Tahap 3b: field graph, diisi/dikoreksi setelah process_stages tersedia
    workflow_sequence: list[str] = Field(default_factory=list)
    process_edges: list[dict[str, Any]] = Field(default_factory=list)
    entry_stages: list[str] = Field(default_factory=list)
    terminal_stages: list[str] = Field(default_factory=list)
    parallel_groups: list[dict[str, Any]] | None = None
    lanes: list[str] = Field(default_factory=list)


# --- Tahap 2: Asset ---

class AssetManualInput(BaseDocumentSchema):
    asset_id: str
    asset_name: str
    category: str
    units_available: int = Field(default=0, ge=0)
    capacity_per_unit: CapacityMetricInput | None = None
    total_capacity: CapacityMetricInput | None = None
    automation_level: Literal["manual", "semi_automated", "automated"] | None = None
    is_automated: bool = False
    operational_cost_per_hour: float = Field(default=0.0, ge=0)
    currency: str = "IDR"
    environmental_factors: EnvironmentalFactorsInput | None = None
    metric_derivation_reasoning: str | None = None


# --- Tahap 3: Process Stage ---

class ProcessStageManualInput(BaseDocumentSchema):
    stage_id: str
    stage_name: str
    lane: str
    next_stage_id: str | None = None
    is_terminal: bool = False
    asset_id: str
    operator_task: str
    material_input: list[str] = Field(default_factory=list)
    material_output: list[str] = Field(default_factory=list)
    material_per_batch: list[dict[str, Any]] = Field(default_factory=list)
    flow_type: str
    cycle_time_seconds: float = Field(gt=0)
    throughput: CapacityMetricInput
    throughput_per_hour: float | None = None
    automation_level: str
    qc_requirement: str
    metric_derivation_reasoning: str | None = None


# --- Tahap 4: Shift ---

_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ShiftManualInput(BaseDocumentSchema):
    shift_id: str
    start_time: str  # format "HH:MM"
    end_time: str  # format "HH:MM"
    duration_hours: float | None = None  # auto-kalkulasi bila kosong
    crosses_midnight: bool | None = None  # auto-derive bila kosong

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not _TIME_PATTERN.match(v):
            raise ValueError(f"Format jam tidak valid: '{v}' (harus HH:MM, mis. 08:00)")
        return v


# --- Tahap 5: Job Desk ---

class JobDeskDemandsInput(BaseDocumentSchema):
    physical_demand_level: Literal["low", "medium", "high"]
    task_complexity: float = Field(ge=0, le=1)
    error_severity: Literal["minor", "moderate", "severe"]
    required_cognitive_focus: float = Field(ge=0, le=1)


class JobDeskManualInput(BaseDocumentSchema):
    job_id: str
    allocation_id: str | None = None
    job_title: str
    stage_id: str  # WAJIB: harus dipilih dari daftar process_stages pada payload yang sama
    assigned_asset_id: str  # WAJIB: harus dipilih dari daftar assets pada payload yang sama
    assigned_worker_ids: list[str] = Field(default_factory=list)
    shift_id: str  # WAJIB: harus dipilih dari daftar shifts pada payload yang sama
    headcount: int = Field(default=1, ge=1)
    demands: JobDeskDemandsInput
    qc_requirement: str
    metric_derivation_reasoning: str | None = None


# --- Tahap 6: Worker ---

class WorkerManualInput(BaseDocumentSchema):
    worker_id: str
    name: str
    demographics: dict[str, Any]
    shift_context: dict[str, Any]
    skills: list[str] | None = None
    certifications: list[str] | None = None
    capabilities: list[str] | None = None

    @field_validator("demographics", "shift_context")
    @classmethod
    def must_not_be_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("Field ini wajib diisi minimal 1 key (tidak boleh objek kosong).")
        return v


# --- Tahap 7: Compatibility Evaluation ---

class CompatibilityEvaluationManualInput(BaseDocumentSchema):
    worker_id: str  # WAJIB: harus ada di daftar workers pada payload yang sama
    job_id: str  # WAJIB: harus ada di daftar job_desks pada payload yang sama
    asset_id: str | None = None  # opsional, tapi jika diisi harus ada di daftar assets
    evaluations: dict[str, Any]
    llm_reasoning: str | None = None


# --- Payload Gabungan (menggantikan upload template.pdf + workers.zip) ---

class ProcessCombinedDocumentsManualRequest(BaseDocumentSchema):
    """
    Payload lengkap dari form frontend, menggantikan `template` (PDF) + `worker_zip` (ZIP)
    pada endpoint otomatis. Field-nya sengaja identik dengan Tahap 1-7 di
    spesifikasi-flowchart-form-manual.md agar frontend bisa submit satu kali di akhir alur.
    """

    factory_info: FactoryInfoManualInput
    assets: list[AssetManualInput] = Field(default_factory=list)
    process_stages: list[ProcessStageManualInput] = Field(default_factory=list)
    shifts: list[ShiftManualInput] = Field(default_factory=list)
    job_desks: list[JobDeskManualInput] = Field(default_factory=list)
    workers: list[WorkerManualInput] = Field(default_factory=list)
    compatibility_evaluations: list[CompatibilityEvaluationManualInput] = Field(default_factory=list)

    # True bila user sengaja memperbarui factory_id yang sudah ada (bukan membuat baru).
    # Default False -> D01 akan menolak bila factory_id sudah terdaftar.
    overwrite_existing_factory: bool = False


class ProcessCombinedDocumentsManualResponse(BaseDocumentSchema):
    parse_job_id: str | None = None
    factory_id: str
    workers_parsed: int = 0
    job_desks_parsed: int = 0
    warnings: list[str] = Field(default_factory=list)

# ==========================================================================
# SKEMA JOB BACKGROUND TAHAP 5 (Matriks Kompatibilitas Asinkron)
# ==========================================================================

CompatibilityJobStatus = Literal["queued", "running", "success", "error"]


class CompatibilityJobRequest(BaseDocumentSchema):
    """
    Payload untuk menjadwalkan Tahap 5 di background worker. Hanya mendukung
    mode `factoryId` -- mode stateless (factoryStructure + workerProfile) tetap
    dilayani secara sinkron oleh `POST /documents/step-5`.
    """

    factory_id: str
    max_workers: int = Field(default=4, ge=1, le=32)
    max_attempts: int = Field(default=3, ge=1, le=10)
    strict_compatibility: bool = False
    persist: bool = True


class CompatibilityJobResponse(BaseDocumentSchema):
    job_id: str
    factory_id: str
    status: CompatibilityJobStatus
    total_pairs: int = 0
    completed_pairs: int = 0
    progress_percent: float = 0.0
    evaluations_persisted: int = 0
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]] | None = None
    failed_pairs: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_stage: str | None = None
    error_message: str | None = None
    error_details: list[Any] | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    @classmethod
    def from_job(cls, job: Any) -> "CompatibilityJobResponse":
        total = job.total_pairs or 0
        completed = job.completed_pairs or 0
        percent = round(completed / total * 100, 2) if total else 0.0
        return cls(
            job_id=job.job_id,
            factory_id=job.factory_id,
            status=job.status,
            total_pairs=total,
            completed_pairs=completed,
            progress_percent=100.0 if job.status == "success" else percent,
            evaluations_persisted=job.evaluations_persisted or 0,
            compatibility_matrix=job.compatibility_matrix,
            failed_pairs=job.failed_pairs or [],
            warnings=job.warnings or [],
            error_stage=job.error_stage,
            error_message=job.error_message,
            error_details=job.error_details,
            created_at=job.created_at.isoformat() if job.created_at else None,
            started_at=job.started_at.isoformat() if job.started_at else None,
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
        )