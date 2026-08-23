"""
Layanan bisnis (service layer) modul Digital Twin Ingestion.
Sesuai dengan Standar Kontrak Data Digital Twin System.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.digital_twin_ingestion import models, schemas
from app.modules.digital_twin_ingestion.repository import DigitalTwinRepository


class DigitalTwinService:
    """Service layer untuk mengelola ingesti dan retrieval data Digital Twin."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = DigitalTwinRepository(db)

    async def _resolve_factory_id(self, job_id: str | int | None) -> str | None:
        """Resolve factory_id berdasarkan job_id (ID Parse Job / Audit Log)."""
        if not job_id:
            return None

        job_str = str(job_id).strip()

        # 1. Jika job_id berupa digit/angka, cari factory_id dari DocumentParseJob
        if job_str.isdigit():
            try:
                from app.modules.documents.models import DocumentParseJob

                stmt_job = select(DocumentParseJob).where(DocumentParseJob.id == int(job_str))
                res_job = await self.db.execute(stmt_job)
                parse_job = res_job.scalar_one_or_none()
                if parse_job:
                    if parse_job.factory_id:
                        return parse_job.factory_id
                    if parse_job.factory_structure and isinstance(
                        parse_job.factory_structure, dict
                    ):
                        fac_info = parse_job.factory_structure.get("factory_info", {})
                        if fac_info.get("factory_id"):
                            return fac_info.get("factory_id")
                    return f"FAC-{parse_job.id}"
            except Exception:
                pass

        # 2. Cari langsung ke tabel Factory berdasarkan exact match atau pattern suffix (-job{id})
        stmt_fac = select(models.Factory.factory_id).where(
            (models.Factory.factory_id == job_str)
            | (models.Factory.factory_id.like(f"%-job{job_str}"))
        )
        res_fac = await self.db.execute(stmt_fac)
        factory_id = res_fac.scalar_one_or_none()
        if factory_id:
            return factory_id

        # Fallback jika tidak ditemukan di DB, kembalikan string job_str langsung
        return job_str

    async def get_full_twin(self, job_id: str | int | None = None) -> schemas.DigitalTwin:
        """
        Mengambil data Digital Twin lengkap dari database berdasarkan job_id.
        Jika job_id tidak diberikan, akan mengambil factory paling terbaru.
        Jika database belum terisi, mengembalikan struktur DigitalTwin kosong secara dinamis.
        """
        factory_id = await self._resolve_factory_id(job_id)

        query = select(models.Factory).options(
            selectinload(models.Factory.assets),
            selectinload(models.Factory.process_stages),
            selectinload(models.Factory.shifts),
            selectinload(models.Factory.job_desks),
            selectinload(models.Factory.workers),
            selectinload(models.Factory.flow_snapshots).selectinload(
                models.FactoryFlowSnapshot.staff_positions
            ),
            selectinload(models.Factory.evaluations),
        )

        if factory_id:
            query = query.where(models.Factory.factory_id == factory_id)
        else:
            query = query.order_by(models.Factory.created_at.desc())

        result = await self.db.execute(query)
        factory = result.scalars().first()

        # Fallback dinamis jika database belum terisi / factory tidak ditemukan
        if not factory:
            return schemas.DigitalTwin(
                factory_info=schemas.FactoryInfo(
                    factory_id=factory_id or "",
                    factory_name="",
                    process_type="serial",
                    declared_worker_count=0,
                    registered_worker_count=0,
                    layout_description="",
                    workflow_sequence=[],
                    process_edges=[],
                    entry_stages=[],
                    terminal_stages=[],
                    parallel_groups=[],
                    lanes=[],
                ),
                assets=[],
                process_stages=[],
                shifts=[],
                job_desks=[],
                workers=[],
                factory_flow_rightnow=None,
                llm_compatibility_and_evaluations=[],
                warnings=[
                    f"Data Digital Twin untuk Job ID '{job_id}' belum tersedia."
                    if job_id
                    else "Data Digital Twin belum tersedia. Silakan lakukan parsing dokumen terlebih dahulu."
                ],
            )

        # Pemetaan Worker Name untuk Staff Position Lookup
        worker_name_map = {w.worker_id: w.name for w in factory.workers}

        # Pemrosesan Flow Snapshot terbaru
        latest_snapshot = factory.flow_snapshots[-1] if factory.flow_snapshots else None
        factory_flow = None
        if latest_snapshot:
            snapshot_ts = latest_snapshot.snapshot_timestamp
            formatted_timestamp = (
                snapshot_ts.isoformat() if isinstance(snapshot_ts, datetime) else str(snapshot_ts)
            )

            factory_flow = schemas.FactoryFlowRightNow(
                snapshot_timestamp=formatted_timestamp,
                note=latest_snapshot.note,
                staff_current_positions=[
                    schemas.StaffPosition(
                        worker_id=sp.worker_id,
                        name=worker_name_map.get(sp.worker_id, ""),
                        current_station=sp.current_station,
                        current_asset_id=sp.current_asset_id,
                        activity_status=sp.activity_status,
                        moving_to_next_step=sp.moving_to_next_step,
                        handoff_item=sp.handoff_item,
                    )
                    for sp in latest_snapshot.staff_positions
                ],
            )

        # Pemrosesan Matriks Kompatibilitas Flattened
        evaluations_list = []
        for e in factory.evaluations:
            eval_payload = (
                e.evaluations
                if isinstance(e.evaluations, dict)
                else (e.evaluations.__dict__ if hasattr(e.evaluations, "__dict__") else {})
            )
            evaluations_list.append(
                schemas.CompatibilityEvaluation(
                    worker_id=e.worker_id,
                    job_id=e.job_id,
                    asset_id=getattr(e, "asset_id", None),
                    evaluations=eval_payload,
                    llm_reasoning=e.llm_reasoning or "",
                )
            )

        return schemas.DigitalTwin(
            factory_info=schemas.FactoryInfo(
                factory_id=factory.factory_id,
                factory_name=factory.factory_name,
                process_type=factory.process_type or "serial",
                declared_worker_count=factory.declared_worker_count or 0,
                registered_worker_count=factory.registered_worker_count or 0,
                layout_description=factory.layout_description or "",
                workflow_sequence=factory.workflow_sequence or [],
                process_edges=[
                    schemas.ProcessEdge(**pe) for pe in (factory.process_edges or [])
                ],
                entry_stages=factory.entry_stages or [],
                terminal_stages=factory.terminal_stages or [],
                parallel_groups=(
                    [schemas.ParallelGroup(**pg) for pg in factory.parallel_groups]
                    if factory.parallel_groups
                    else []
                ),
                lanes=factory.lanes or [],
            ),
            assets=[
                schemas.Asset(
                    asset_id=a.asset_id,
                    asset_name=a.asset_name,
                    category=a.category,
                    units_available=a.units_available,
                    capacity_per_unit=schemas.Quantity(**(a.capacity_per_unit or {})),
                    total_capacity=schemas.Quantity(**(a.total_capacity or {})),
                    automation_level=a.automation_level,
                    is_automated=a.is_automated,
                    operational_cost_per_hour=a.operational_cost_per_hour,
                    currency=a.currency,
                    environmental_factors=schemas.AssetEnvironmentalFactors(
                        **(a.environmental_factors or {})
                    ),
                    metric_derivation_reasoning=a.metric_derivation_reasoning,
                )
                for a in factory.assets
            ],
            process_stages=[
                schemas.ProcessStage(
                    stage_id=s.stage_id,
                    stage_name=s.stage_name,
                    lane=s.lane,
                    next_stage_id=s.next_stage_id,
                    is_terminal=s.is_terminal,
                    asset_id=s.asset_id,
                    operator_task=s.operator_task,
                    material_input=s.material_input or [],
                    material_output=s.material_output or [],
                    material_per_batch=[
                        schemas.Quantity(**q) for q in (s.material_per_batch or [])
                    ],
                    flow_type=s.flow_type,
                    cycle_time_seconds=s.cycle_time_seconds,
                    throughput=schemas.Quantity(**(s.throughput or {})),
                    throughput_per_hour=s.throughput_per_hour,
                    automation_level=s.automation_level,
                    qc_requirement=s.qc_requirement,
                    metric_derivation_reasoning=s.metric_derivation_reasoning,
                )
                for s in factory.process_stages
            ],
            shifts=[
                schemas.Shift(
                    shift_id=sh.shift_id,
                    start_time=sh.start_time,
                    end_time=sh.end_time,
                    duration_hours=sh.duration_hours,
                    crosses_midnight=sh.crosses_midnight,
                )
                for sh in factory.shifts
            ],
            job_desks=[
                schemas.JobDesk(
                    job_id=j.job_id,
                    allocation_id=j.allocation_id,
                    job_title=j.job_title,
                    stage_id=j.stage_id,
                    assigned_asset_id=j.assigned_asset_id,
                    assigned_worker_ids=j.assigned_worker_ids or [],
                    shift_id=j.shift_id,
                    headcount=j.headcount,
                    demands=schemas.Demands(**(j.demands or {})),
                    qc_requirement=j.qc_requirement,
                    metric_derivation_reasoning=j.metric_derivation_reasoning,
                )
                for j in factory.job_desks
            ],
            workers=[
                schemas.Worker(
                    worker_id=w.worker_id,
                    name=w.name,
                    demographics=schemas.Demographics(**(w.demographics or {})),
                    shift_context=schemas.ShiftContext(**(w.shift_context or {})),
                    skills=w.skills,
                    certifications=w.certifications,
                    capabilities=w.capabilities,
                )
                for w in factory.workers
            ],
            factory_flow_rightnow=factory_flow,
            llm_compatibility_and_evaluations=evaluations_list,
            warnings=getattr(factory, "warnings", []) or [],
        )

    async def get_assets(self, job_id: str | int | None = None) -> list[schemas.Asset]:
        twin = await self.get_full_twin(job_id)
        return twin.assets

    async def get_process_stages(self, job_id: str | int | None = None) -> list[schemas.ProcessStage]:
        twin = await self.get_full_twin(job_id)
        return twin.process_stages

    async def get_workers(self, job_id: str | int | None = None) -> list[schemas.Worker]:
        twin = await self.get_full_twin(job_id)
        return twin.workers

    async def get_job_desks(self, job_id: str | int | None = None) -> list[schemas.JobDesk]:
        twin = await self.get_full_twin(job_id)
        return twin.job_desks

    async def get_compatibility_matrix(
        self, job_id: str | int | None = None
    ) -> list[schemas.CompatibilityEvaluation]:
        twin = await self.get_full_twin(job_id)
        return twin.llm_compatibility_and_evaluations

    async def get_live_flow(
        self, job_id: str | int | None = None
    ) -> schemas.FactoryFlowRightNow | None:
        twin = await self.get_full_twin(job_id)
        return twin.factory_flow_rightnow

    async def save_digital_twin(self, twin: schemas.DigitalTwin) -> None:
        await self.repository.save_full_snapshot(twin)