"""
backend/app/modules/documents/schemas.py

Skema data modul documents (Pipeline Terpadu, Kombinasi Tahap 1-5, & Tahap 3 s/d 5).
Sesuai dengan Standar Kontrak Data Digital Twin System.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
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
    worker_profile: dict[str, Any]
    worker_agent_input: str
    candidates_found: int = 0
    rejected_blocks_count: int = 0
    archive_reports: list[ArchiveReportSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --- Skema Kombinasi (Tahap 1, 2, 4, & 5) ---

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
    factory_structure: dict[str, Any]
    worker_profile: dict[str, Any]
    max_workers: int = 4
    max_attempts: int = 3
    strict_compatibility: bool = False


class Step5Response(BaseDocumentSchema):
    compatibility_matrix: dict[str, Any] | list[dict[str, Any]]
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


class FactoryListItemResponse(BaseModel):
    factory_id: str = Field(..., alias="factoryId")
    factory_name: str = Field(..., alias="factoryName")
    workers_count: int = Field(..., alias="workersCount")
    job_desks_count: int = Field(..., alias="jobDesksCount")
    created_at: Optional[str] = Field(None, alias="createdAt")

    class Config:
        populate_by_name = True