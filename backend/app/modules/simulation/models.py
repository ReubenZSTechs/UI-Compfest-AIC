# backend/app/modules/simulation/models.py
"""
Model ORM parameter simulasi.

Seluruh foreign key ke modul `digital_twin_ingestion` bersifat composite dan
selalu menyertakan `factory_id`, mengikuti composite primary key yang dipakai
di sana. Ini menutup kemungkinan satu baris simulasi merujuk entitas milik
pabrik lain hanya karena id-nya kebetulan sama.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SimulationStation(Base):
    """
    Satu row = satu stasiun (ordinal 1..N) untuk satu factory. Menggabungkan
    materials_by_ordinal, step_names, step_cost_base, capacity_by_ordinal,
    batch_in/out_by_ordinal, dan cycle_ticks_by_ordinal -- semuanya diindeks
    per ordinal, jadi cukup satu tabel.

    `stage_id` menautkan stasiun ke ProcessStage asalnya secara eksplisit.
    Sebelumnya tautan ini diterka lewat pencocokan nama
    (`station.step_name == stage.stage_name`), yang tabrakan begitu ada dua
    stage bernama sama dalam satu pabrik.

    ondelete CASCADE, bukan SET NULL: FK ini composite dan salah satu kolomnya
    (`factory_id`) NOT NULL, sehingga SET NULL akan mencoba menihilkan
    factory_id juga dan gagal. CASCADE juga lebih tepat secara semantik --
    stasiun simulasi tidak punya arti tanpa stage asalnya.

    Cardinality: satu row per (factory_id, ordinal); unique constraint mencegah
    duplikasi stasiun dalam factory yang sama.
    """
    __tablename__ = "simulation_stations"
    __table_args__ = (
        UniqueConstraint("factory_id", "ordinal", name="uq_simulation_stations_factory_ordinal"),
        ForeignKeyConstraint(
            ["factory_id", "stage_id"],
            ["process_stages.factory_id", "process_stages.stage_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

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
    """
    Singleton config per factory (threshold, warehouse, jadwal shift).
    `factory_id` sekaligus primary key -- memaksa satu baris per pabrik.

    `warehouse_step_id` HARUS sama persis dengan `WAREHOUSE_STEP_ID` di frontend
    `simulation.types.ts`; kalau berubah di satu sisi, sisi lain wajib menyusul.
    """
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
    """
    1:1 dengan Worker, dipisah ke modul simulation supaya data identitas worker
    (HR) tidak bercampur dengan parameter tuning simulasi -- dua concern dengan
    siklus edit yang berbeda.

    `factory_id` didenormalisasi ke sini sehingga query per-pabrik (baca maupun
    hapus) bisa langsung memfilter kolom lokal, tanpa subquery ke tabel
    `workers` seperti implementasi sebelumnya.

    PK: (factory_id, worker_id) -- satu multiplier per worker per pabrik.
    """
    __tablename__ = "worker_throughput_multipliers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
        ),
    )

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    worker_id: Mapped[str] = mapped_column(String, primary_key=True)
    multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SimulationSeedAssignment(Base):
    """
    Penugasan worker -> job -> asset yang diedit admin.

    `realtime_metrics_cache` BUKAN sumber kebenaran -- itu cache hasil kalkulasi
    terakhir (fatigue/stress/throughput). Dihitung ulang tiap simulasi start;
    kolom ini hanya untuk audit/preview di admin panel.

        realtime_metrics_cache (JSONB, nullable):
            {
                "current_fatigue_level": 0.62,
                "current_stress_level": 0.48,
                "effective_throughput_per_hour": 205.0,
                "effective_error_probability": 0.03,
                "burnout_hazard_risk": "medium",
                "throughput_multiplier": 1.15
            }

    Cardinality: maksimal satu row per (factory_id, worker_id).
    """
    __tablename__ = "simulation_seed_assignments"
    __table_args__ = (
        UniqueConstraint("factory_id", "worker_id", name="uq_simulation_seed_factory_worker"),
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["factory_id", "assigned_job_id"],
            ["job_desks.factory_id", "job_desks.job_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["factory_id", "assigned_asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True
    )
    worker_id: Mapped[str] = mapped_column(String, nullable=False)
    assigned_job_id: Mapped[str] = mapped_column(String, nullable=False)
    assigned_asset_id: Mapped[str] = mapped_column(String, nullable=False)

    realtime_metrics_cache: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


__all__ = [
    "SimulationStation",
    "SimulationSettings",
    "WorkerThroughputMultiplier",
    "SimulationSeedAssignment",
]