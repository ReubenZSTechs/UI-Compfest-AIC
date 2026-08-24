# backend/app/modules/documents/models.py
"""
Model ORM untuk audit trail / riwayat eksekusi document-parser (Tahap 1-5 & Kombinasi 1-5).
Sesuai dengan Standar Kontrak Data Digital Twin System.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.digital_twin_ingestion.models import Factory


class DocumentParseJob(Base):
    """
    Riwayat/audit trail eksekusi pipeline document-parser (Tahap 1-5 & Kombinasi).

    Tabel ini mencatat riwayat proses parsing baik secara modular maupun terpadu/kombinasi:
    - Tahap 1: Ekstraksi dokumen PDF template pabrik
    - Tahap 2: Output struktur pabrik dari Agent A (`factory_structure`)
    - Tahap 3: Hasil pemeriksaan kelengkapan (blocking/warning gaps)
    - Tahap 4: Ekstraksi arsip ZIP CV/catatan wawancara & output profil pekerja dari Agent B (`worker_profile`)
    - Tahap 5: Matriks kompatibilitas pekerja x job desk (`compatibility_matrix`)
    - Kombinasi Tahap 1-5: Pemrosesan sekaligus dokumen template pabrik (1+2), ZIP CV pekerja (4), 
      dan generasi matriks kompatibilitas (5) dalam satu pipeline.

    Kepatuhan Standar Kontrak Data:
    1. `job_desks_parsed`: Menampung kalkulasi eksplisit len(job_desks) setelah fallback mapping dari job_descriptions.
    2. `workers_parsed`: Menampung kalkulasi eksplisit len(workers).
    3. `compatibility_matrix`: Mendukung penampungan objek dict maupun array flattened
       (`llm_compatibility_and_evaluations`).
    4. Seluruh bidang data disimpan dalam format `snake_case` di basis data.
    """

    __tablename__ = "document_parse_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str | None] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    template_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    cv_bundle_filename: Mapped[str | None] = mapped_column(String, nullable=True)

    # Metrics & Audit Trail (Kalkulasi Eksplisit)
    workers_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_desks_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # list[str]
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    error_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[Any], nullable (bisa berisi list string maupun list dictionary laporan error)
    error_details: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # Snapshot mentah tiap tahap (Mendukung struktur dict maupun list flattened)
    factory_structure: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    worker_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    compatibility_matrix: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB, nullable=True)
    floor_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped[Factory | None] = relationship()

class CompatibilityMatrixJob(Base):
    """
    State satu eksekusi Tahap 5 (matriks kompatibilitas) yang dijalankan di
    background worker, bukan di dalam siklus request HTTP.

    Tahap 5 memanggil agent LLM sebanyak (jumlah worker x jumlah job desk).
    Untuk 10 worker x 10 job desk itu 100 panggilan dalam satu request -- lewat
    batas timeout reverse proxy mana pun. Baris ini menyimpan status & progres
    eksekusi sehingga frontend cukup melakukan polling.

    Alur status: queued -> running -> success | error.
    `stale` dipakai saat proses backend restart di tengah eksekusi, sehingga job
    yang menggantung tidak selamanya tampak `running` di UI.
    """

    __tablename__ = "compatibility_matrix_jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)

    total_pairs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_pairs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evaluations_persisted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    max_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    strict_compatibility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    persist_result: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    compatibility_matrix: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB, nullable=True)
    failed_pairs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    error_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    factory: Mapped[Factory | None] = relationship()