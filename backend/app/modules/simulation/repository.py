# backend/app/modules/simulation/repository.py
"""
Persistence layer modul simulation.

Menyimpan dua kelompok tabel sekaligus untuk satu factory_id:
1. Struktur digital twin (Asset, ProcessStage, Shift, JobDesk) -- didelegasikan ke
   `documents.repository.persist_factory_structure` supaya hanya ada satu jalur
   penulisan struktur pabrik di seluruh backend.
2. Parameter simulasi (SimulationStation, SimulationSettings,
   WorkerThroughputMultiplier, SimulationSeedAssignment).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion.models import (
    Asset,
    CompatibilityEvaluation,
    Factory,
    JobDesk,
    ProcessStage,
    Shift,
    Worker,
)
from app.modules.simulation.models import (
    SimulationSeedAssignment,
    SimulationSettings,
    SimulationStation,
    WorkerThroughputMultiplier,
)


class SimulationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_worker_ids(self, factory_id: str) -> set[str]:
        stmt = select(Worker.worker_id).where(Worker.factory_id == factory_id)
        return set((await self.db.execute(stmt)).scalars().all())

    async def prune_structure(
        self,
        factory_id: str,
        keep_asset_ids: set[str],
        keep_stage_ids: set[str],
        keep_shift_ids: set[str],
        keep_job_ids: set[str],
    ) -> None:
        """Hapus entitas lama yang tidak lagi ada pada flowchart terbaru."""
        await self.db.execute(
            delete(SimulationSeedAssignment).where(
                SimulationSeedAssignment.factory_id == factory_id
            )
        )
        await self.db.execute(
            delete(SimulationStation).where(SimulationStation.factory_id == factory_id)
        )
        await self.db.execute(
            delete(CompatibilityEvaluation).where(
                CompatibilityEvaluation.factory_id == factory_id,
                CompatibilityEvaluation.job_id.notin_(keep_job_ids or {""}),
            )
        )
        await self.db.execute(
            delete(JobDesk).where(
                JobDesk.factory_id == factory_id,
                JobDesk.job_id.notin_(keep_job_ids or {""}),
            )
        )
        await self.db.flush()

        await self.db.execute(
            delete(ProcessStage).where(
                ProcessStage.factory_id == factory_id,
                ProcessStage.stage_id.notin_(keep_stage_ids or {""}),
            )
        )
        await self.db.execute(
            delete(Shift).where(
                Shift.factory_id == factory_id,
                Shift.shift_id.notin_(keep_shift_ids or {""}),
            )
        )
        await self.db.flush()

        await self.db.execute(
            delete(Asset).where(
                Asset.factory_id == factory_id,
                Asset.asset_id.notin_(keep_asset_ids or {""}),
            )
        )
        await self.db.flush()

    async def replace_stations(
        self, factory_id: str, stations: list[dict[str, Any]]
    ) -> int:
        await self.db.execute(
            delete(SimulationStation).where(SimulationStation.factory_id == factory_id)
        )
        await self.db.flush()

        for station in stations:
            self.db.add(SimulationStation(factory_id=factory_id, **station))

        await self.db.flush()
        return len(stations)

    async def upsert_settings(self, factory_id: str, settings: dict[str, Any]) -> None:
        row = await self.db.get(SimulationSettings, factory_id)
        if row is None:
            row = SimulationSettings(factory_id=factory_id)
            self.db.add(row)
        for key, value in settings.items():
            setattr(row, key, value)
        await self.db.flush()

    async def replace_worker_multipliers(
        self, factory_id: str, multipliers: dict[str, float]
    ) -> int:
        await self.db.execute(
            delete(WorkerThroughputMultiplier).where(
                WorkerThroughputMultiplier.factory_id == factory_id
            )
        )
        await self.db.flush()

        for worker_id, multiplier in multipliers.items():
            self.db.add(
                WorkerThroughputMultiplier(
                    factory_id=factory_id, worker_id=worker_id, multiplier=multiplier
                )
            )

        await self.db.flush()
        return len(multipliers)

    async def replace_seed_assignments(
        self, factory_id: str, assignments: list[dict[str, Any]]
    ) -> int:
        await self.db.execute(
            delete(SimulationSeedAssignment).where(
                SimulationSeedAssignment.factory_id == factory_id
            )
        )
        await self.db.flush()

        for assignment in assignments:
            self.db.add(SimulationSeedAssignment(factory_id=factory_id, **assignment))

        await self.db.flush()
        return len(assignments)

    async def load_stations(self, factory_id: str) -> list[SimulationStation]:
        stmt = (
            select(SimulationStation)
            .where(SimulationStation.factory_id == factory_id)
            .order_by(SimulationStation.ordinal)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def load_settings(self, factory_id: str) -> SimulationSettings | None:
        return await self.db.get(SimulationSettings, factory_id)

    async def load_worker_multipliers(self, factory_id: str) -> dict[str, float]:
        stmt = select(WorkerThroughputMultiplier).where(
            WorkerThroughputMultiplier.factory_id == factory_id
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return {row.worker_id: row.multiplier for row in rows}

    async def load_seed_assignments(
        self, factory_id: str
    ) -> list[SimulationSeedAssignment]:
        stmt = (
            select(SimulationSeedAssignment)
            .where(SimulationSeedAssignment.factory_id == factory_id)
            .order_by(SimulationSeedAssignment.worker_id)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def load_structure(
        self, factory_id: str
    ) -> tuple[Factory | None, list[ProcessStage], list[JobDesk]]:
        factory = await self.db.get(Factory, factory_id)
        if factory is None:
            return None, [], []

        stages = list(
            (
                await self.db.execute(
                    select(ProcessStage).where(ProcessStage.factory_id == factory_id)
                )
            )
            .scalars()
            .all()
        )
        jobs = list(
            (
                await self.db.execute(
                    select(JobDesk).where(JobDesk.factory_id == factory_id)
                )
            )
            .scalars()
            .all()
        )
        return factory, stages, jobs

    async def latest_configured_factory_id(self) -> str | None:
        stmt = (
            select(SimulationSettings.factory_id)
            .order_by(SimulationSettings.updated_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def load_factory(self, factory_id: str) -> Factory | None:
        return await self.db.get(Factory, factory_id)

    async def load_job_desks(self, factory_id: str) -> list[JobDesk]:
        stmt = select(JobDesk).where(JobDesk.factory_id == factory_id)
        return list((await self.db.execute(stmt)).scalars().all())