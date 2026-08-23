# app/modules/rl_optimization/models.py
"""
SQLAlchemy models untuk domain RL Optimization.

REVISI (bug fix -- table name collision):
Sebelumnya modul ini punya model class SENDIRI untuk Factory/Asset/JobDesk/
Worker/CompatibilityEvaluation, MENDUPLIKASI tabel `factories`/`assets`/
`workers`/`compatibility_evaluations` yang juga didefinisikan di
`app.modules.digital_twin_ingestion.models`. Begitu kedua modul model
di-import bersamaan (mis. lewat Alembic autogenerate atau
`Base.metadata.create_all`), SQLAlchemy melempar
`InvalidRequestError: Table 'factories' is already defined for this
MetaData instance` -- ditemukan & dikonfirmasi lewat pengujian end-to-end.

Root cause sebenarnya: `service.get_digital_twin()` sudah di-refactor
(iterasi sebelumnya) untuk delegasi ke `DigitalTwinService` milik
`digital_twin_ingestion` -- jadi model Factory/Asset/JobDesk/Worker/
CompatibilityEvaluation di modul INI sudah tidak pernah dipakai untuk
query/insert apa pun. Kelasnya dihapus di sini; `OptimizationJob` di
bawah tetap referensi `factories.factory_id` sebagai FK -- itu sekarang
otomatis merujuk ke tabel `factories` milik `digital_twin_ingestion`
(satu-satunya definisi yang tersisa), bukan tabel duplikat.

`LiveSimulationState` juga dihapus (bukan cuma di-skip) -- tabel ini
mewakili "state simulasi live yang dihitung & disimpan backend", yang
bertentangan dengan arsitektur Client-Side Simulation yang sudah
diputuskan (lihat penghapusan `GET /simulation/live` endpoint). Membiarkan
model-nya tetap ada mengundang orang menyambungkannya lagi di masa depan
tanpa sadar itu regresi arsitektur.

Yang tersisa: `OptimizationJob` & `OptimizationScenario` -- keduanya masih
relevan sebagai record ASINKRON hasil training RL (bukan live tick state),
konsisten dengan endpoint `POST /rl-optimization/optimize` dkk yang tetap
ada.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# =============================================================================
# Enums (dipakai sebagai Postgres ENUM type lewat SQLAlchemy Enum)
# =============================================================================

class OptimizationJobStatusEnum(str, PyEnum):
    queued = "queued"
    running = "running"
    converged = "converged"
    failed = "failed"


# =============================================================================
# Optimization — job async + hasil skenario
# =============================================================================

class OptimizationJob(Base, TimestampMixin):
    __tablename__ = "optimization_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), index=True)

    status: Mapped[OptimizationJobStatusEnum] = mapped_column(
        Enum(OptimizationJobStatusEnum, native_enum=False, length=32),
        nullable=False,
        default=OptimizationJobStatusEnum.queued,
    )
    algorithm: Mapped[str] = mapped_column(String(128), nullable=False, default="Maskable PPO (sb3-contrib)")
    total_episodes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    progress_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    constraints: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{hiring_allowed, fire_or_mutation_allowed, automation_allowed, capex_rp}",
    )
    baseline: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Diisi saat job selesai: {throughput_per_hour, human_error_rate_pct, total_op_cost_per_hour_rp}"
    )
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    scenarios: Mapped[list["OptimizationScenario"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class OptimizationScenario(Base, TimestampMixin):
    __tablename__ = "optimization_scenarios"
    __table_args__ = (
        UniqueConstraint("job_id", "scenario_id", name="uq_scenario_per_job"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("optimization_jobs.job_id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="mis. 'scenario_01'")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{throughput_per_hour, human_error_rate_pct, total_op_cost_per_hour_rp} masing2 {before,after,delta_pct,direction}",
    )
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    assumption_flag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    factory_flow_optimal: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{note, reallocation_moves, asset_upgrades, new_hires, new_cross_compatibility_evaluations, optimal_staff_positions, residual_bottleneck, rl_reasoning}",
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="Diisi saat scenario ini di-apply ke live_simulation_states"
    )
    applied_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    job: Mapped["OptimizationJob"] = relationship(back_populates="scenarios")