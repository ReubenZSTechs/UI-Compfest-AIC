# backend/app/modules/digital_twin_ingestion/service.py
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

    async def get_full_twin(self, factory_id: str | None = None) -> schemas.DigitalTwin:
        """
        Mengambil data Digital Twin lengkap dari database.
        Jika factory_id tidak diberikan, akan mengambil factory paling terbaru.
        Jika database belum terisi, mengembalikan struktur DigitalTwin kosong secara dinamis.
        """
        query = select(models.Factory).options(
            selectinload(models.Factory.assets),
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
                    workflow_sequence=[],
                ),
                assets=[],
                job_desks=[],
                workers=[],
                factory_flow_rightnow=None,
                llm_compatibility_and_evaluations=[],
                warnings=[
                    "Data Digital Twin belum tersedia. Silakan lakukan parsing dokumen terlebih dahulu."
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
                workflow_sequence=factory.workflow_sequence,
                process_type=factory.process_type,
                declared_worker_count=factory.declared_worker_count,
                layout_description=factory.layout_description,
                parallel_groups=(
                    [schemas.ParallelGroup(**pg) for pg in factory.parallel_groups]
                    if factory.parallel_groups
                    else None
                ),
            ),
            assets=[
                schemas.Asset(
                    asset_id=a.asset_id,
                    asset_name=a.asset_name,
                    category=a.category,
                    workflow_step=a.workflow_step,
                    is_automated=a.is_automated,
                    base_throughput_capacity=a.base_throughput_capacity,
                    operational_cost_per_hour=a.operational_cost_per_hour,
                    environmental_factors=schemas.EnvironmentalFactors(**(a.environmental_factors or {})),
                    metric_derivation_reasoning=a.metric_derivation_reasoning,
                    units_available=a.units_available,
                )
                for a in factory.assets
            ],
            job_desks=[
                schemas.JobDesk(
                    job_id=j.job_id,
                    job_title=j.job_title,
                    workflow_step=j.workflow_step,
                    assigned_asset_id=j.assigned_asset_id,
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

    async def get_assets(self, factory_id: str | None = None) -> list[schemas.Asset]:
        twin = await self.get_full_twin(factory_id)
        return twin.assets

    async def get_workers(self, factory_id: str | None = None) -> list[schemas.Worker]:
        twin = await self.get_full_twin(factory_id)
        return twin.workers

    async def get_job_desks(self, factory_id: str | None = None) -> list[schemas.JobDesk]:
        twin = await self.get_full_twin(factory_id)
        return twin.job_desks

    async def get_compatibility_matrix(
        self, factory_id: str | None = None
    ) -> list[schemas.CompatibilityEvaluation]:
        twin = await self.get_full_twin(factory_id)
        return twin.llm_compatibility_and_evaluations

    async def get_live_flow(
        self, factory_id: str | None = None
    ) -> schemas.FactoryFlowRightNow | None:
        twin = await self.get_full_twin(factory_id)
        return twin.factory_flow_rightnow

    async def save_digital_twin(self, twin: schemas.DigitalTwin) -> None:
        await self.repository.save_full_snapshot(twin)