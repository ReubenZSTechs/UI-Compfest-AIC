from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Factory(Base):
    __tablename__ = "factories"

    factory_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_name: Mapped[str] = mapped_column(String, nullable=False)
    workflow_sequence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assets: Mapped[list["Asset"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    workers: Mapped[list["Worker"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    flow_snapshots: Mapped[list["FactoryFlowSnapshot"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    evaluations: Mapped[list["CompatibilityEvaluation"]] = relationship(back_populates="factory", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    workflow_step: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    base_throughput_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    operational_cost_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    # { noise_level_db, vibration_hazard_level, physical_strain_index }
    environmental_factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="assets")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="assigned_asset")


class JobDesk(Base):
    __tablename__ = "job_desks"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    workflow_step: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)
    # { required_cognitive_focus, physical_demand_level, task_complexity, error_severity }
    demands: Mapped[dict] = mapped_column(JSONB, nullable=False)
    qc_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_derivation_reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="job_desks")
    assigned_asset: Mapped["Asset"] = relationship(back_populates="job_desks")


class Worker(Base):
    __tablename__ = "workers"

    worker_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # { age, gender, years_of_experience, baseline_physical_stamina, cognitive_resilience }
    demographics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # { hours_worked_today, consecutive_shifts }
    shift_context: Mapped[dict] = mapped_column(JSONB, nullable=False)

    factory: Mapped["Factory"] = relationship(back_populates="workers")


class FactoryFlowSnapshot(Base):
    """Satu row = satu snapshot factory_flow_rightnow (bisa banyak seiring waktu)."""
    __tablename__ = "factory_flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="flow_snapshots")
    staff_positions: Mapped[list["StaffPosition"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class StaffPosition(Base):
    __tablename__ = "staff_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("factory_flow_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False)
    current_station: Mapped[str] = mapped_column(String, nullable=False)
    current_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id"), nullable=False)
    activity_status: Mapped[str] = mapped_column(String, nullable=False)
    moving_to_next_step: Mapped[str] = mapped_column(String, nullable=False)
    handoff_item: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped["FactoryFlowSnapshot"] = relationship(back_populates="staff_positions")


class CompatibilityEvaluation(Base):
    __tablename__ = "compatibility_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("job_desks.job_id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    # { overall_compatibility_score, throughput_multiplier, error_multiplier,
    #   fatigue_accumulation_rate, stress_sensitivity_factor }
    evaluations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="evaluations")