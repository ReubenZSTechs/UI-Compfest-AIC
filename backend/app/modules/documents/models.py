"""
backend/app/modules/documents/models.py

Model ORM untuk audit trail / riwayat eksekusi document-parser (Tahap 1-5 & Kombinasi 1-5).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.digital_twin_ingestion.models import Factory


class DocumentParseJob(Base):
    """
    Riwayat/audit trail eksekusi pipeline document-parser (Tahap 1-5 & Kombinasi).

    Tabel ini mencatat riwayat proses parsing baik secara modular maupun terpadu/kombinasi:
    - Tahap 1: Ekstraksi dokumen PDF template pabrik
    - Tahap 2: Output struktur pabrik dari Agent A
    - Tahap 3: Hasil pemeriksaan kelengkapan (blocking/warning gaps)
    - Tahap 4: Ekstraksi arsip ZIP CV/catatan wawancara & output profil pekerja dari Agent B
    - Tahap 5: Matriks kompatibilitas pekerja x job desk
    - Kombinasi Tahap 1-5: Pemrosesan sekaligus dokumen template pabrik (1+2), ZIP CV pekerja (4), 
      dan generasi matriks kompatibilitas (5) dalam satu pipeline.

    Catatan:
        - `template_filename` & `cv_bundle_filename` dibuat nullable agar dapat
          diisi secara parsial (pada endpoint individual) atau terisi bersamaan
          (pada endpoint kombinasi Tahap 1, 2, 4, & 5).
        - `cv_bundle_filename` menyimpan nama berkas .zip arsip pekerja.
        - `floor_state` tetap dipertahankan sebagai field JSONB nullable untuk
          kompatibilitas skema basis data, namun dilewati/dikosongkan pada alur ini.

    Sumber data:
        status              : "success" | "error" | "in_progress"
        template_filename    : nama file PDF/dokumen template pabrik (Tahap 1 / Kombinasi)
        cv_bundle_filename   : nama berkas .zip arsip pekerja (Tahap 4 / Kombinasi)
        workers_parsed        : jumlah worker yang berhasil diproses oleh Agent B (Tahap 4)
        job_desks_parsed      : jumlah job desk yang berhasil diproses (Tahap 2)
        warnings (JSONB, list[str]) : peringatan non-fatal akumulatif
        error_stage (nullable): tahap kegagalan ("upload"/"extract"/"llm_parse"/"validate"/"compatibility")
        error_message (nullable): pesan error utama saat gagal
        error_details (JSONB, list[Any], nullable): rincian error (mis. blocking_gaps Tahap 3 / laporan ZIP gagal)
        factory_structure (JSONB, nullable): snapshot MENTAH output Agent A (Tahap 2)
        worker_profile (JSONB, nullable): snapshot MENTAH output Agent B (Tahap 4)
        compatibility_matrix (JSONB, nullable): snapshot MENTAH output Tahap 5
        floor_state (JSONB, nullable): opsional / dilewati (Tahap 6 skipped)

    FK: factory_id nullable & ondelete="SET NULL" -- jika pipeline gagal sebelum
    factory_id diketahui, row tetap tercatat dengan factory_id NULL.
    """

    __tablename__ = "document_parse_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str | None] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    template_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    cv_bundle_filename: Mapped[str | None] = mapped_column(String, nullable=True)

    workers_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_desks_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # list[str]
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    error_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # list[Any], nullable (bisa berisi list string maupun list dictionary laporan error)
    error_details: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # Snapshot mentah tiap tahap
    factory_structure: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    worker_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    compatibility_matrix: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    floor_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship()