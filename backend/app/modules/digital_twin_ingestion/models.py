from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint,
    Integer, PrimaryKeyConstraint, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Factory(Base):
    """
    Root entity: satu pabrik/factory sebagai parent dari seluruh data digital twin.
    Selaras dengan factory_md.schema.json -> factory_info.

    CATATAN: factory_id di-generate ULANG agar selalu unik per proses parsing
    (lihat DigitalTwinRepository._generate_unique_factory_id), meskipun LLM
    menghasilkan factory_id yang identik untuk dokumen sumber yang sama persis.
    Ini memastikan setiap parsing selalu menghasilkan Digital Twin BARU yang
    independen, bukan menimpa/bentrok dengan hasil parsing sebelumnya.
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

    PK komposit (factory_id, asset_id): asset_id yang di-generate LLM (mis. "ast-01")
    bersifat generik dan wajar bertabrakan antar-factory berbeda, sama seperti kasus
    worker_id. Composite key memastikan asset_id hanya perlu unik DI DALAM satu factory.
    """
    __tablename__ = "assets"
    __table_args__ = (
        PrimaryKeyConstraint("factory_id", "asset_id", name="pk_assets"),
    )

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"))
    asset_id: Mapped[str] = mapped_column(String)
    asset_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    units_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_per_unit: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_capacity: Mapped[dict] = mapped_column(JSONB, nullable=False)
    automation_level: Mapped[str] = mapped_column(String, nullable=False)
    is_automated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    operational_cost_per_hour: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="IDR")
    environmental_factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metric_derivation_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    factory: Mapped["Factory"] = relationship(back_populates="assets")
    process_stages: Mapped[list["ProcessStage"]] = relationship(back_populates="asset")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="assigned_asset")


class ProcessStage(Base):
    """
    Satu tahapan proses produksi. Sesuai factory_md.schema.json -> process_stages[].

    PK komposit (factory_id, stage_id). asset_id direferensikan lewat FK komposit
    ke Asset(factory_id, asset_id) -- bukan lagi single-column -- karena Asset kini
    juga di-scope per-factory.
    """
    __tablename__ = "process_stages"
    __table_args__ = (
        PrimaryKeyConstraint("factory_id", "stage_id", name="pk_process_stages"),
        ForeignKeyConstraint(
            ["factory_id", "asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="RESTRICT",
            name="fk_process_stages_asset",
        ),
    )

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"))
    stage_id: Mapped[str] = mapped_column(String)
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
    asset: Mapped["Asset"] = relationship(back_populates="process_stages")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="stage")


class Shift(Base):
    """
    Definisi shift kerja. Sesuai factory_md.schema.json -> shifts[].
    PK komposit (factory_id, shift_id).
    """
    __tablename__ = "shifts"
    __table_args__ = (
        PrimaryKeyConstraint("factory_id", "shift_id", name="pk_shifts"),
    )

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"))
    shift_id: Mapped[str] = mapped_column(String)
    start_time: Mapped[str] = mapped_column(String, nullable=False)
    end_time: Mapped[str] = mapped_column(String, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    factory: Mapped["Factory"] = relationship(back_populates="shifts")
    job_desks: Mapped[list["JobDesk"]] = relationship(back_populates="shift")


class JobDesk(Base):
    """
    Posisi/peran kerja spesifik pada satu ProcessStage, terikat ke satu Asset & satu Shift.
    Sesuai factory_md.schema.json -> job_descriptions[].

    PK komposit (factory_id, job_id). Seluruh FK ke stage_id, assigned_asset_id, dan
    shift_id kini komposit karena tabel induknya juga di-scope per-factory.
    """
    __tablename__ = "job_desks"
    __table_args__ = (
        PrimaryKeyConstraint("factory_id", "job_id", name="pk_job_desks"),
        ForeignKeyConstraint(
            ["factory_id", "stage_id"],
            ["process_stages.factory_id", "process_stages.stage_id"],
            ondelete="RESTRICT",
            name="fk_job_desks_stage",
        ),
        ForeignKeyConstraint(
            ["factory_id", "assigned_asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="RESTRICT",
            name="fk_job_desks_asset",
        ),
        ForeignKeyConstraint(
            ["factory_id", "shift_id"],
            ["shifts.factory_id", "shifts.shift_id"],
            ondelete="RESTRICT",
            name="fk_job_desks_shift",
        ),
    )

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(String)
    allocation_id: Mapped[str] = mapped_column(String, nullable=False)
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
    assigned_asset: Mapped["Asset"] = relationship(back_populates="job_desks")
    stage: Mapped["ProcessStage"] = relationship(back_populates="job_desks")
    shift: Mapped["Shift"] = relationship(back_populates="job_desks")


class Worker(Base):
    """
    Data pekerja/staf pabrik. worker_id di-scope per-factory (bukan unik global),
    karena Agent B (LLM) men-generate ID generik (wrk-01, wrk-02, ...) yang wajar
    bertabrakan antar-factory berbeda.
    """
    __tablename__ = "workers"
    __table_args__ = (
        PrimaryKeyConstraint("factory_id", "worker_id", name="pk_workers"),
    )

    factory_id: Mapped[str] = mapped_column(ForeignKey("factories.factory_id", ondelete="CASCADE"))
    worker_id: Mapped[str] = mapped_column(String)
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
    factory_id ditambahkan agar FK ke Worker & Asset bisa komposit (mengikuti
    scoping per-factory yang sama seperti tabel lain).
    """
    __tablename__ = "staff_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
            name="fk_staff_positions_worker",
        ),
        ForeignKeyConstraint(
            ["factory_id", "current_asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            name="fk_staff_positions_asset",
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
    """
    Hasil evaluasi kompatibilitas worker x job_desk x asset.
    worker_id, job_id, asset_id kini semuanya direferensikan via FK komposit
    karena tabel induknya (Worker, JobDesk, Asset) di-scope per-factory.
    """
    __tablename__ = "compatibility_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["factory_id", "worker_id"],
            ["workers.factory_id", "workers.worker_id"],
            ondelete="CASCADE",
            name="fk_compatibility_evaluations_worker",
        ),
        ForeignKeyConstraint(
            ["factory_id", "job_id"],
            ["job_desks.factory_id", "job_desks.job_id"],
            ondelete="CASCADE",
            name="fk_compatibility_evaluations_job",
        ),
        ForeignKeyConstraint(
            ["factory_id", "asset_id"],
            ["assets.factory_id", "assets.asset_id"],
            ondelete="CASCADE",
            name="fk_compatibility_evaluations_asset",
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