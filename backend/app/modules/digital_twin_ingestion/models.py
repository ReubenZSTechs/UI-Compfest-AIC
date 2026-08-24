# backend/app/modules/digital_twin_ingestion/models.py
"""
Model ORM Digital Twin.

SCOPING: seluruh entitas anak (Asset, ProcessStage, Shift, JobDesk, Worker)
memakai composite primary key `(factory_id, <entity_id>)`. Sebelumnya PK-nya
hanya `<entity_id>` sehingga bersifat global -- dua pabrik yang sama-sama
memakai id generik seperti "ast-01" akan saling menimpa, dan
`persist_factory_structure()` (yang melakukan `session.get(Asset, asset_id)`)
diam-diam memindahkan kepemilikan baris ke factory terakhir yang menulis.

Konsekuensinya seluruh foreign key antar-entitas ikut menjadi composite dan
selalu menyertakan `factory_id`, sehingga relasi lintas-pabrik tidak mungkin
terbentuk bahkan bila id anaknya kebetulan sama.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Factory(Base):
    """
    Root entity: satu pabrik/factory sebagai parent dari seluruh data digital twin.
    Selaras dengan factory_md.schema.json -> factory_info.
    """
    __tablename__ = "factories"

    factory_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_name: Mapped[str] = mapped_column(String, nullable=False)
    process_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    declared_worker_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    registered_worker_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    layout_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workflow_sequence: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    process_edges: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    entry_stages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    terminal_stages: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    parallel_groups: Mapped[Optional[list[dict]]] = mapped_column(JSONB, nullable=True)
    lanes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assets: Mapped[list["Asset"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    process_stages: Mapped[list["ProcessStage"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    workers: Mapped[list["Worker"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    flow_snapshots: Mapped[list["FactoryFlowSnapshot"]] = relationship(back_populates="factory", cascade="all, delete-orphan")
    evaluations: Mapped[list["CompatibilityEvaluation"]] = relationship(back_populates="factory", cascade="all, delete-orphan")


class Asset(Base):
    """
    Mesin/peralatan/stasiun kerja. Sesuai factory_md.schema.json -> assets[].
    PK: (factory_id, asset_id).
    """
    __tablename__ = "assets"

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    units_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_per_unit: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    total_capacity: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    automation_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    operational_cost_per_hour: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.0)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="IDR")
    environmental_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metric_derivation_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factory: Mapped["Factory"] = relationship(back_populates="assets")
    process_stages: Mapped[list["ProcessStage"]] = relationship(back_populates="asset", viewonly=True)
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="assigned_asset", viewonly=True)


class ProcessStage(Base):
    """
    Satu tahapan proses produksi. Sesuai factory_md.schema.json -> process_stages[].
    PK: (factory_id, stage_id).

    `next_stage_id` sengaja TIDAK diberi foreign key: relasi ini self-referential
    dan sering diisi sebelum stage tujuannya di-insert dalam batch yang sama.
    Validasinya dilakukan di service layer (`_validate_design`).
    """
    __tablename__ = "process_stages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="RESTRICT",
        ),
    )

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    stage_id: Mapped[str] = mapped_column(String, primary_key=True)
    stage_name: Mapped[str] = mapped_column(String, nullable=False)
    lane: Mapped[str] = mapped_column(String, nullable=False)
    next_stage_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asset_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    operator_task: Mapped[str] = mapped_column(Text, nullable=False)
    material_input: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    material_output: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    material_per_batch: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    flow_type: Mapped[str] = mapped_column(String, nullable=False)
    cycle_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    throughput: Mapped[dict] = mapped_column(JSONB, nullable=False)
    throughput_per_hour: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    automation_level: Mapped[str] = mapped_column(String, nullable=False)
    qc_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_derivation_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factory: Mapped["Factory"] = relationship(back_populates="process_stages")
    asset: Mapped["Asset"] = relationship(back_populates="process_stages", viewonly=True)
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="stage", viewonly=True)


class Shift(Base):
    """
    Definisi shift kerja. Sesuai factory_md.schema.json -> shifts[].
    PK: (factory_id, shift_id).
    """
    __tablename__ = "shifts"

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    shift_id: Mapped[str] = mapped_column(String, primary_key=True)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    factory: Mapped["Factory"] = relationship(back_populates="shifts")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="shift", viewonly=True)


class JobDesk(Base):
    """
    Posisi/peran kerja spesifik pada satu ProcessStage, terikat ke satu Asset & satu Shift.
    Sesuai factory_md.schema.json -> job_descriptions[]. PK: (factory_id, job_id).
    """
    __tablename__ = "job_desks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "stage_id"],
            ["process_stages.factory_id", "process_stages.stage_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["factory_id", "assigned_asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["factory_id", "shift_id"],
            ["shifts.factory_id", "shifts.shift_id"],
            ondelete="RESTRICT",
        ),
    )

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    allocation_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    stage_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assigned_asset_id: Mapped[str] = mapped_column(String, nullable=False)
    assigned_worker_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    shift_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    demands: Mapped[dict] = mapped_column(JSONB, nullable=False)
    qc_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    metric_derivation_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factory: Mapped["Factory"] = relationship(back_populates="job_desks")
    assigned_asset: Mapped["Asset"] = relationship(back_populates="job_desks", viewonly=True)
    stage: Mapped["ProcessStage"] = relationship(back_populates="job_desks", viewonly=True)
    shift: Mapped["Shift"] = relationship(back_populates="job_desks", viewonly=True)


class Worker(Base):
    """
    Data pekerja/staf pabrik, terpisah atribut statis (demographics) dan
    atribut dinamis harian (shift_context). PK: (factory_id, worker_id).
    """
    __tablename__ = "workers"

    factory_id: Mapped[str] = mapped_column(
        ForeignKey("factories.factory_id", ondelete="CASCADE"), primary_key=True
    )
    worker_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    demographics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    shift_context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    skills: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    certifications: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)
    capabilities: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True)

    factory: Mapped["Factory"] = relationship(back_populates="workers")


class FactoryFlowSnapshot(Base):
    """Satu row = satu snapshot kondisi lantai produksi pada satu titik waktu."""
    __tablename__ = "factory_flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="flow_snapshots")
    staff_positions: Mapped[list["StaffPosition"]] = relationship(back_populates="snapshot", cascade="all, delete-orphan")


class StaffPosition(Base):
    """
    Posisi & aktivitas satu worker pada satu snapshot tertentu.
    `factory_id` didenormalisasi ke sini supaya FK ke Worker & Asset bisa
    composite (scoped per pabrik) tanpa perlu join ke snapshot induknya.
    """
    __tablename__ = "staff_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["factory_id", "current_asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("factory_flow_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String, nullable=False)
    current_station: Mapped[str] = mapped_column(String, nullable=False)
    current_asset_id: Mapped[str] = mapped_column(String, nullable=False)
    activity_status: Mapped[str] = mapped_column(String, nullable=False)
    moving_to_next_step: Mapped[str] = mapped_column(String, nullable=False)
    handoff_item: Mapped[str] = mapped_column(Text, nullable=False)

    snapshot: Mapped["FactoryFlowSnapshot"] = relationship(back_populates="staff_positions")


class CompatibilityEvaluation(Base):
    """Hasil evaluasi kompatibilitas worker x job_desk x asset."""
    __tablename__ = "compatibility_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["factory_id", "job_id"],
            ["job_desks.factory_id", "job_desks.job_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["factory_id", "asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    asset_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evaluations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    factory: Mapped["Factory"] = relationship(back_populates="evaluations")


__all__ = [
    "Factory",
    "Asset",
    "ProcessStage",
    "Shift",
    "JobDesk",
    "Worker",
    "FactoryFlowSnapshot",
    "StaffPosition",
    "CompatibilityEvaluation",
]