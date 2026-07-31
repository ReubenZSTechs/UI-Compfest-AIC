from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulationStation(Base):
    """Satu row = satu stasiun (ordinal 1..10) untuk satu factory.
    Gabungan dari materials_by_ordinal, step_names, step_cost_base,
    capacity_by_ordinal, batch_in/out_by_ordinal, cycle_ticks_by_ordinal
    -- semua field lama itu sama-sama diindex per ordinal, jadi satu tabel."""
    __tablename__ = "simulation_stations"
    __table_args__ = (UniqueConstraint("factory_id", "ordinal", name="uq_simulation_stations_factory_ordinal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)  # posisi 1..10 dalam workflow

    step_name: Mapped[str] = mapped_column(String, nullable=False)
    material_name: Mapped[str] = mapped_column(String, nullable=False)
    material_unit: Mapped[str] = mapped_column(String, nullable=False)

    step_cost_base: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    batch_in: Mapped[float] = mapped_column(Float, nullable=False)
    batch_out: Mapped[float] = mapped_column(Float, nullable=False)
    cycle_ticks: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    factory: Mapped["Factory"] = relationship()  # type: ignore[name-defined]  # noqa: F821


class SimulationSettings(Base):
    """Singleton config per factory (threshold, warehouse, jadwal shift)."""
    __tablename__ = "simulation_settings"

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True)

    bottleneck_fill_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    idle_qty_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    station_1_safety_margin: Mapped[float] = mapped_column(Float, nullable=False)

    warehouse_capacity: Mapped[float] = mapped_column(Float, nullable=False)
    warehouse_feed_rate: Mapped[float] = mapped_column(Float, nullable=False)
    warehouse_step_id: Mapped[str] = mapped_column(String, nullable=False)

    shift_start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    break_start_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)
    break_end_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)
    shift_end_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)

    analytical_insight_summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_output_units: Mapped[float] = mapped_column(Float, nullable=False)
    initial_batch_seq: Mapped[int] = mapped_column(Integer, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkerThroughputMultiplier(Base):
    """1:1 dengan Worker (module digital_twin_ingestion). Dipisah ke module
    simulation supaya tidak mencampur data 'identitas worker' (HR) dengan
    'parameter tuning simulasi' -- dua concern yang siklus editnya beda."""
    __tablename__ = "worker_throughput_multipliers"

    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), primary_key=True)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SimulationSeedAssignment(Base):
    """Penugasan worker -> job -> asset yang diedit admin.
    `realtime_metrics` BUKAN sumber kebenaran -- itu cache hasil kalkulasi
    terakhir dari service (fatigue/stress/throughput formula, sama seperti
    generate_full_compatibility_matrix di module digital_twin_ingestion).
    Dihitung ulang tiap kali simulasi start; kolom ini cuma buat audit/preview
    di admin panel tanpa perlu re-run kalkulasi."""
    __tablename__ = "simulation_seed_assignments"
    __table_args__ = (UniqueConstraint("factory_id", "worker_id", name="uq_simulation_seed_factory_worker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE"), nullable=False)
    assigned_job_id: Mapped[str] = mapped_column(ForeignKey("job_desks.job_id", ondelete="RESTRICT"), nullable=False)
    assigned_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)

    # { current_fatigue_level, current_stress_level, effective_throughput_per_hour,
    #   effective_error_probability, burnout_hazard_risk, throughput_multiplier }
    realtime_metrics_cache: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())