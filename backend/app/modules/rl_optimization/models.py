# app/modules/rl_optimization/models.py
"""
SQLAlchemy models untuk domain RL Optimization.

Struktur mengikuti factory_workflow_digital_twin.json:
- Factory, Asset, JobDesk, Worker, CompatibilityEvaluation -> "digital twin" statis
- LiveSimulationState                                      -> kondisi real-time
- OptimizationJob, OptimizationScenario                     -> hasil training RL

Nested object yang sifatnya deskriptif/tidak sering di-query per-field
(mis. environmental_factors, demographics, factory_flow_optimal) disimpan
sebagai kolom JSON, bukan dinormalisasi habis-habisan — trade-off yang
wajar untuk data hasil LLM synthesis yang bentuknya masih bisa berevolusi.
Kolom JSON pakai tipe generik `JSON` (bukan `JSONB` postgres-only) supaya
model tetap portable untuk testing (SQLite) maupun produksi (Postgres);
Postgres akan tetap menyimpannya secara efisien, dan bisa di-migrasi ke
JSONB nanti kalau butuh index GIN untuk query dalam JSON.
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
# Digital Twin — statis
# =============================================================================

class Factory(Base, TimestampMixin):
    __tablename__ = "factories"

    factory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    factory_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_sequence: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="Urutan step, mis. ['step_01_weighing', ...]"
    )

    assets: Mapped[list["Asset"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    workers: Mapped[list["Worker"]] = relationship(back_populates="factory", cascade="all, delete-orphan")


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), index=True)

    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_step: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_throughput_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    operational_cost_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    environmental_factors: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="{noise_level_db, vibration_hazard_level, physical_strain_index}"
    )
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="assets")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="asset")


class JobDesk(Base, TimestampMixin):
    __tablename__ = "job_desks"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), index=True)
    assigned_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), index=True)

    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_step: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    demands: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="{required_cognitive_focus, physical_demand_level, task_complexity, error_severity}"
    )
    qc_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="job_desks")
    asset: Mapped["Asset"] = relationship(back_populates="job_desks")


class Worker(Base, TimestampMixin):
    __tablename__ = "workers"

    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    demographics: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{age, gender, years_of_experience, baseline_physical_stamina, cognitive_resilience}",
    )
    shift_context: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="{hours_worked_today, consecutive_shifts}"
    )

    factory: Mapped["Factory"] = relationship(back_populates="workers")


class CompatibilityEvaluation(Base, TimestampMixin):
    """Satu baris matriks kompatibilitas N x M (worker x job x asset)."""

    __tablename__ = "compatibility_evaluations"
    __table_args__ = (
        UniqueConstraint("worker_id", "job_id", "asset_id", name="uq_compat_worker_job_asset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_desks.job_id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="CASCADE"), index=True)

    evaluations: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{overall_compatibility_score, throughput_multiplier, error_multiplier, fatigue_accumulation_rate, stress_sensitivity_factor}",
    )
    llm_reasoning: Mapped[str] = mapped_column(Text, nullable=False)


# =============================================================================
# Live Simulation State — real-time, satu baris terkini per factory
# =============================================================================

class LiveSimulationState(Base, TimestampMixin):
    """
    Satu baris = snapshot terkini satu factory. Dianggap "current state",
    bukan history — kalau butuh riwayat time-series, tambahkan tabel
    terpisah `live_simulation_state_history` yang append-only.
    """

    __tablename__ = "live_simulation_states"

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    snapshot_timestamp: Mapped[datetime] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    staff_current_positions: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="list[StaffCurrentPosition] — lihat schemas.py"
    )
    current_assignments: Mapped[list] = mapped_column(
        JSON, nullable=False, comment="list[CurrentAssignment] termasuk calculated_realtime_metrics"
    )
    system_bottlenecks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    analytical_insight_summary: Mapped[str] = mapped_column(Text, nullable=False)


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