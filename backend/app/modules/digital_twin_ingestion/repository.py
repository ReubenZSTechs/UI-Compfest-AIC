# backend/app/modules/digital_twin_ingestion/repository.py
"""
Repository layer modul Digital Twin Ingestion.
Sesuai dengan Standar Kontrak Data Digital Twin System.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.digital_twin_ingestion import models, schemas


class DigitalTwinRepository:
    """Repository untuk pengelolaan persistence data Digital Twin ke basis data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_factory_by_id(self, factory_id: str) -> models.Factory | None:
        """
        Mengambil entity Factory beserta seluruh relasi terkait berdasarkan factory_id.
        """
        query = (
            select(models.Factory)
            .where(models.Factory.factory_id == factory_id)
            .options(
                selectinload(models.Factory.assets),
                selectinload(models.Factory.job_desks),
                selectinload(models.Factory.workers),
                selectinload(models.Factory.flow_snapshots).selectinload(
                    models.FactoryFlowSnapshot.staff_positions
                ),
                selectinload(models.Factory.evaluations),
            )
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def delete_factory_if_exists(self, factory_id: str) -> None:
        """
        Menghapus data pabrik beserta seluruh child record terkait jika sudah ada sebelumnya
        untuk mencegah Primary Key / Unique Constraint Conflict saat re-parsing.
        """
        existing_factory = await self.db.get(models.Factory, factory_id)
        if existing_factory:
            await self.db.delete(existing_factory)
            await self.db.flush()

    async def save_full_snapshot(self, data: schemas.DigitalTwin) -> models.Factory:
        """
        Menyimpan snapshot lengkap Digital Twin ke database.
        Jika factory_id sudah ada, data lama akan dihapus terlebih dahulu (upsert behavior).
        Mencatatkan array flattened llm_compatibility_and_evaluations secara konsisten.
        """
        factory_id = data.factory_info.factory_id

        # 1. Bersihkan data pabrik lama jika ada (penanganan re-parsing/overwrite)
        await self.delete_factory_if_exists(factory_id)

        # 2. Simpan entity Factory utama
        factory = models.Factory(
            factory_id=factory_id,
            factory_name=data.factory_info.factory_name,
            workflow_sequence=data.factory_info.workflow_sequence,
            process_type=data.factory_info.process_type,
            declared_worker_count=data.factory_info.declared_worker_count,
            layout_description=data.factory_info.layout_description,
            parallel_groups=(
                [
                    pg.model_dump() if isinstance(pg, BaseModel) else pg
                    for pg in data.factory_info.parallel_groups
                ]
                if data.factory_info.parallel_groups
                else None
            ),
        )
        self.db.add(factory)

        # 3. Simpan Asset / Mesin
        for a in data.assets:
            env_factors = (
                a.environmental_factors.model_dump()
                if isinstance(a.environmental_factors, BaseModel)
                else a.environmental_factors
            )
            self.db.add(
                models.Asset(
                    asset_id=a.asset_id,
                    factory_id=factory.factory_id,
                    asset_name=a.asset_name,
                    category=a.category,
                    workflow_step=a.workflow_step,
                    is_automated=a.is_automated,
                    base_throughput_capacity=a.base_throughput_capacity,
                    operational_cost_per_hour=a.operational_cost_per_hour,
                    environmental_factors=env_factors,
                    metric_derivation_reasoning=a.metric_derivation_reasoning,
                    units_available=a.units_available,
                )
            )

        # 4. Simpan Job Desk (Mendukung entitas terpadu job_desks)
        for j in data.job_desks:
            demands_dict = (
                j.demands.model_dump()
                if isinstance(j.demands, BaseModel)
                else j.demands
            )
            self.db.add(
                models.JobDesk(
                    job_id=j.job_id,
                    factory_id=factory.factory_id,
                    job_title=j.job_title,
                    workflow_step=j.workflow_step,
                    assigned_asset_id=j.assigned_asset_id,
                    demands=demands_dict,
                    qc_requirement=j.qc_requirement,
                    metric_derivation_reasoning=j.metric_derivation_reasoning,
                )
            )

        # 5. Simpan Worker / Pekerja (Atribut Demografi & Shift Context)
        for w in data.workers:
            demographics_dict = (
                w.demographics.model_dump()
                if isinstance(w.demographics, BaseModel)
                else w.demographics
            )
            shift_context_dict = (
                w.shift_context.model_dump()
                if isinstance(w.shift_context, BaseModel)
                else w.shift_context
            )
            self.db.add(
                models.Worker(
                    worker_id=w.worker_id,
                    factory_id=factory.factory_id,
                    name=w.name,
                    demographics=demographics_dict,
                    shift_context=shift_context_dict,
                    skills=w.skills,
                    certifications=w.certifications,
                    capabilities=w.capabilities,
                )
            )

        # 6. Simpan Flow Snapshot & Position (Opsional)
        if data.factory_flow_rightnow:
            snapshot_time = data.factory_flow_rightnow.snapshot_timestamp
            if isinstance(snapshot_time, str):
                snapshot_time = datetime.fromisoformat(
                    snapshot_time.replace("Z", "+00:00")
                )

            snapshot = models.FactoryFlowSnapshot(
                factory_id=factory.factory_id,
                snapshot_timestamp=snapshot_time,
                note=data.factory_flow_rightnow.note,
            )
            self.db.add(snapshot)
            await self.db.flush()  # Dapatkan snapshot.id untuk FK staff_positions

            for sp in data.factory_flow_rightnow.staff_current_positions:
                self.db.add(
                    models.StaffPosition(
                        snapshot_id=snapshot.id,
                        worker_id=sp.worker_id,
                        current_station=sp.current_station,
                        current_asset_id=sp.current_asset_id,
                        activity_status=sp.activity_status,
                        moving_to_next_step=sp.moving_to_next_step,
                        handoff_item=sp.handoff_item,
                    )
                )

        # 7. Simpan Matriks Kompatibilitas Evaluasi LLM (Array Flattened: worker_id, job_id, evaluations, llm_reasoning)
        for ev in data.llm_compatibility_and_evaluations:
            evals_dict = (
                ev.evaluations.model_dump()
                if isinstance(ev.evaluations, BaseModel)
                else (ev.evaluations if isinstance(ev.evaluations, dict) else {})
            )
            self.db.add(
                models.CompatibilityEvaluation(
                    factory_id=factory.factory_id,
                    worker_id=ev.worker_id,
                    job_id=ev.job_id,
                    asset_id=getattr(ev, "asset_id", None),
                    evaluations=evals_dict,
                    llm_reasoning=ev.llm_reasoning,
                )
            )

        await self.db.commit()
        return factory