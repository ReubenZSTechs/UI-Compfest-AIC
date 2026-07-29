# app/modules/rl_optimization/repository.py
"""
Repository layer — HANYA query DB (CRUD), tanpa business logic.

Aturan main modul ini:
- Tidak ada validasi bisnis di sini (mis. "apakah job boleh di-apply") —
  itu tanggung jawab service.py.
- Tidak melempar HTTPException — kalau data tidak ada, return None
  (biarkan service.py yang memutuskan mau raise exception domain apa).
- Semua fungsi menerima AsyncSession dari luar (dependency injection),
  tidak membuat session sendiri.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.rl_optimization import models


# =============================================================================
# Factory & Digital Twin
# =============================================================================

async def get_factory(db: AsyncSession, factory_id: str) -> Optional[models.Factory]:
    result = await db.execute(select(models.Factory).where(models.Factory.factory_id == factory_id))
    return result.scalar_one_or_none()


async def get_digital_twin(db: AsyncSession, factory_id: str) -> Optional[models.Factory]:
    """Eager-load semua relasi sekaligus supaya tidak N+1 query saat serialisasi ke schema."""
    result = await db.execute(
        select(models.Factory)
        .where(models.Factory.factory_id == factory_id)
        .options(
            selectinload(models.Factory.assets),
            selectinload(models.Factory.job_descriptions),
            selectinload(models.Factory.workers),
        )
    )
    return result.scalar_one_or_none()


async def get_compatibility_entries(db: AsyncSession, factory_id: str) -> list[models.CompatibilityEvaluation]:
    result = await db.execute(
        select(models.CompatibilityEvaluation).where(models.CompatibilityEvaluation.factory_id == factory_id)
    )
    return list(result.scalars().all())


async def upsert_factory(db: AsyncSession, factory_id: str, factory_name: str, workflow_sequence: list) -> models.Factory:
    factory = await get_factory(db, factory_id)
    if factory is None:
        factory = models.Factory(factory_id=factory_id, factory_name=factory_name, workflow_sequence=workflow_sequence)
        db.add(factory)
    else:
        factory.factory_name = factory_name
        factory.workflow_sequence = workflow_sequence
    await db.flush()
    return factory


async def replace_assets(db: AsyncSession, factory_id: str, assets_data: list[dict]) -> list[models.Asset]:
    """Hapus semua asset lama milik factory ini, ganti dengan yang baru (dipakai saat re-ingestion)."""
    await db.execute(delete(models.Asset).where(models.Asset.factory_id == factory_id))
    new_assets = [models.Asset(factory_id=factory_id, **data) for data in assets_data]
    db.add_all(new_assets)
    await db.flush()
    return new_assets


async def replace_job_descriptions(db: AsyncSession, factory_id: str, job_descriptions_data: list[dict]) -> list[models.JobDesk]:
    await db.execute(delete(models.JobDesk).where(models.JobDesk.factory_id == factory_id))
    new_job_descriptions = [models.JobDesk(factory_id=factory_id, **data) for data in job_descriptions_data]
    db.add_all(new_job_descriptions)
    await db.flush()
    return new_job_descriptions


async def replace_workers(db: AsyncSession, factory_id: str, workers_data: list[dict]) -> list[models.Worker]:
    await db.execute(delete(models.Worker).where(models.Worker.factory_id == factory_id))
    new_workers = [models.Worker(factory_id=factory_id, **data) for data in workers_data]
    db.add_all(new_workers)
    await db.flush()
    return new_workers


async def replace_compatibility_entries(
    db: AsyncSession, factory_id: str, entries_data: list[dict]
) -> list[models.CompatibilityEvaluation]:
    await db.execute(
        delete(models.CompatibilityEvaluation).where(models.CompatibilityEvaluation.factory_id == factory_id)
    )
    new_entries = [models.CompatibilityEvaluation(factory_id=factory_id, **data) for data in entries_data]
    db.add_all(new_entries)
    await db.flush()
    return new_entries


# =============================================================================
# Live Simulation State
# =============================================================================

async def get_live_state(db: AsyncSession, factory_id: str) -> Optional[models.LiveSimulationState]:
    result = await db.execute(
        select(models.LiveSimulationState).where(models.LiveSimulationState.factory_id == factory_id)
    )
    return result.scalar_one_or_none()


async def upsert_live_state(
    db: AsyncSession,
    factory_id: str,
    snapshot_timestamp: datetime,
    note: str,
    staff_current_positions: list,
    current_assignments: list,
    system_bottlenecks: list,
    analytical_insight_summary: str,
) -> models.LiveSimulationState:
    state = await get_live_state(db, factory_id)
    if state is None:
        state = models.LiveSimulationState(factory_id=factory_id)
        db.add(state)

    state.snapshot_timestamp = snapshot_timestamp
    state.note = note
    state.staff_current_positions = staff_current_positions
    state.current_assignments = current_assignments
    state.system_bottlenecks = system_bottlenecks
    state.analytical_insight_summary = analytical_insight_summary

    await db.flush()
    return state


# =============================================================================
# Optimization Job & Scenario
# =============================================================================

async def create_optimization_job(
    db: AsyncSession,
    factory_id: str,
    constraints: dict,
    requested_by: str,
) -> models.OptimizationJob:
    job = models.OptimizationJob(
        factory_id=factory_id,
        constraints=constraints,
        requested_by=requested_by,
        status=models.OptimizationJobStatusEnum.queued,
    )
    db.add(job)
    await db.flush()
    return job


async def get_optimization_job(db: AsyncSession, job_id: str) -> Optional[models.OptimizationJob]:
    result = await db.execute(select(models.OptimizationJob).where(models.OptimizationJob.job_id == job_id))
    return result.scalar_one_or_none()


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: models.OptimizationJobStatusEnum,
    *,
    progress_pct: Optional[float] = None,
    total_episodes: Optional[int] = None,
    baseline: Optional[dict] = None,
    error_message: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> Optional[models.OptimizationJob]:
    job = await get_optimization_job(db, job_id)
    if job is None:
        return None

    job.status = status
    if progress_pct is not None:
        job.progress_pct = progress_pct
    if total_episodes is not None:
        job.total_episodes = total_episodes
    if baseline is not None:
        job.baseline = baseline
    if error_message is not None:
        job.error_message = error_message
    if started_at is not None:
        job.started_at = started_at
    if finished_at is not None:
        job.finished_at = finished_at

    await db.flush()
    return job


async def create_scenarios(
    db: AsyncSession, job_id: str, scenarios_data: list[dict]
) -> list[models.OptimizationScenario]:
    scenarios = [models.OptimizationScenario(job_id=job_id, **data) for data in scenarios_data]
    db.add_all(scenarios)
    await db.flush()
    return scenarios


async def list_scenarios(db: AsyncSession, job_id: str) -> list[models.OptimizationScenario]:
    result = await db.execute(
        select(models.OptimizationScenario).where(models.OptimizationScenario.job_id == job_id)
    )
    return list(result.scalars().all())


async def get_scenario(db: AsyncSession, job_id: str, scenario_id: str) -> Optional[models.OptimizationScenario]:
    result = await db.execute(
        select(models.OptimizationScenario).where(
            models.OptimizationScenario.job_id == job_id,
            models.OptimizationScenario.scenario_id == scenario_id,
        )
    )
    return result.scalar_one_or_none()


async def mark_scenario_applied(
    db: AsyncSession, job_id: str, scenario_id: str, applied_by: str, applied_at: datetime
) -> Optional[models.OptimizationScenario]:
    scenario = await get_scenario(db, job_id, scenario_id)
    if scenario is None:
        return None
    scenario.applied_at = applied_at
    scenario.applied_by = applied_by
    await db.flush()
    return scenario