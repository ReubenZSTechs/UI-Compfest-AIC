"""
Layanan bisnis (service layer) modul Digital Twin Ingestion.
Sesuai dengan Standar Kontrak Data Digital Twin System.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.digital_twin_ingestion import models, schemas
from app.modules.digital_twin_ingestion.repository import DigitalTwinRepository

_UNIT_CLASSES = {"mass", "volume", "count", "power", "noise"}
_ASSET_CATEGORIES = {
    "machine",
    "measuring_equipment",
    "conveyor_automation",
    "environmental_chamber",
    "manual_station",
}
_AUTOMATION_LEVELS = {"manual", "semi_automated", "automated"}
_FLOW_TYPES = {"batch", "continuous"}
_HAZARD_LEVELS = {"low", "medium", "high"}
_ERROR_SEVERITIES = {"low", "moderate", "high", "critical"}
_ERROR_SEVERITY_ALIASES = {"minor": "low", "major": "high", "severe": "critical"}
_PROCESS_TYPES = {"serial", "parallel", "hybrid"}


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _as_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _literal(value: Any, allowed: set[str], fallback: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in allowed else fallback


def _pick(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if source.get(key) is not None:
            return source[key]
    return None


def _quantity(raw: Any) -> schemas.Quantity:
    data = raw if isinstance(raw, dict) else {}
    value = _as_float(data.get("value"))
    unit = data.get("unit")
    text = data.get("raw")
    if not text:
        text = f"{value} {unit}" if value is not None and unit else "n/a"
    return schemas.Quantity(
        raw=str(text),
        value=value,
        unit=str(unit) if unit else None,
        unit_class=data.get("unit_class") if data.get("unit_class") in _UNIT_CLASSES else None,
        basis=str(data["basis"]) if data.get("basis") else None,
    )


def _environmental_factors(raw: Any) -> schemas.AssetEnvironmentalFactors:
    data = raw if isinstance(raw, dict) else {}
    return schemas.AssetEnvironmentalFactors(
        power_consumption_watt=_as_float(data.get("power_consumption_watt")),
        noise_level_db=_as_float(data.get("noise_level_db")),
        vibration_hazard_level=_literal(data.get("vibration_hazard_level"), _HAZARD_LEVELS, "low"),
        physical_strain_index=_as_float(data.get("physical_strain_index"), 0.0) or 0.0,
    )


def _demands(raw: Any) -> schemas.Demands:
    data = raw if isinstance(raw, dict) else {}
    severity = str(data.get("error_severity") or "").strip().lower()
    severity = _ERROR_SEVERITY_ALIASES.get(severity, severity)
    return schemas.Demands(
        required_cognitive_focus=_as_float(data.get("required_cognitive_focus"), 0.5) or 0.0,
        physical_demand_level=_literal(data.get("physical_demand_level"), _HAZARD_LEVELS, "medium"),
        task_complexity=_as_float(data.get("task_complexity"), 0.5) or 0.0,
        error_severity=_literal(severity, _ERROR_SEVERITIES, "moderate"),
    )


def _demographics(raw: Any) -> schemas.Demographics:
    data = raw if isinstance(raw, dict) else {}
    return schemas.Demographics(
        age=_as_int(data.get("age"), 30),
        gender=str(data.get("gender") or "unknown"),
        years_of_experience=_as_float(data.get("years_of_experience"), 0.0) or 0.0,
        baseline_physical_stamina=_as_float(data.get("baseline_physical_stamina"), 0.5) or 0.0,
        cognitive_resilience=_as_float(data.get("cognitive_resilience"), 0.5) or 0.0,
    )


def _shift_context(raw: Any) -> schemas.ShiftContext:
    data = raw if isinstance(raw, dict) else {}
    return schemas.ShiftContext(
        hours_worked_today=_as_float(data.get("hours_worked_today"), 0.0) or 0.0,
        consecutive_shifts=_as_int(data.get("consecutive_shifts"), 0),
    )


def _process_edge(raw: Any) -> schemas.ProcessEdge | None:
    data = raw if isinstance(raw, dict) else {}
    source = _pick(data, "from_stage_id", "fromStageId", "from_stage", "from", "source")
    target = _pick(data, "to_stage_id", "toStageId", "to_stage", "to", "target")
    if not source or not target:
        return None
    return schemas.ProcessEdge(from_stage_id=str(source), to_stage_id=str(target))


def _parallel_group(raw: Any) -> schemas.ParallelGroup | None:
    data = raw if isinstance(raw, dict) else {}
    group_id = _pick(data, "group_id", "groupId")
    if not group_id:
        return None
    return schemas.ParallelGroup(
        group_id=str(group_id),
        depth=_as_int(_pick(data, "depth"), 0),
        steps=[str(s) for s in (data.get("steps") or [])],
        lanes=[str(s) for s in (data.get("lanes") or [])],
        converges_to=_pick(data, "converges_to", "convergesTo"),
        reasoning=data.get("reasoning"),
    )


class DigitalTwinService:
    """Service layer untuk mengelola ingesti dan retrieval data Digital Twin."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = DigitalTwinRepository(db)

    # ------------------------------------------------------------------
    # Inisialisasi factory (Langkah 1: pembuatan factory_id)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_factory_id() -> str:
        return f"fac-{uuid.uuid4().hex[:12]}"

    async def create_factory(self, payload: schemas.FactoryCreateRequest) -> models.Factory:
        factory_id = (payload.factory_id or "").strip() or self.generate_factory_id()

        existing = await self.db.get(models.Factory, factory_id)
        if existing is not None:
            raise ValueError(f"factory_id '{factory_id}' sudah terdaftar.")

        factory = models.Factory(
            factory_id=factory_id,
            factory_name=payload.factory_name.strip(),
            process_type=payload.process_type,
            declared_worker_count=payload.declared_worker_count,
            registered_worker_count=0,
            layout_description=payload.layout_description,
            workflow_sequence=[],
            process_edges=[],
            entry_stages=[],
            terminal_stages=[],
            parallel_groups=None,
            lanes=[],
        )
        self.db.add(factory)
        await self.db.commit()
        await self.db.refresh(factory)
        return factory

    async def get_factory(self, factory_id: str) -> models.Factory | None:
        return await self.db.get(models.Factory, factory_id)

    # ------------------------------------------------------------------
    # Ringkasan & status pipeline
    # ------------------------------------------------------------------

    async def _count(self, model: Any, factory_id: str) -> int:
        stmt = select(func.count()).select_from(model).where(model.factory_id == factory_id)
        return int((await self.db.execute(stmt)).scalar_one())

    async def _count_stations(self, factory_id: str) -> int:
        from app.modules.simulation.models import SimulationStation

        return await self._count(SimulationStation, factory_id)

    async def get_summary(self, factory_id: str) -> schemas.FactorySummary | None:
        factory = await self.get_factory(factory_id)
        if factory is None:
            return None

        assets_count = await self._count(models.Asset, factory_id)
        stages_count = await self._count(models.ProcessStage, factory_id)
        shifts_count = await self._count(models.Shift, factory_id)
        job_desks_count = await self._count(models.JobDesk, factory_id)
        workers_count = await self._count(models.Worker, factory_id)
        evaluations_count = await self._count(models.CompatibilityEvaluation, factory_id)
        stations_count = await self._count_stations(factory_id)

        simulation_configured = stations_count > 0 or (stages_count > 0 and job_desks_count > 0)

        if evaluations_count > 0:
            status: Any = "twin_ready"
        elif simulation_configured:
            status = "simulation_configured"
        elif workers_count > 0:
            status = "workers_ingested"
        else:
            status = "initialized"

        return schemas.FactorySummary(
            factory_id=factory.factory_id,
            factory_name=factory.factory_name,
            process_type=factory.process_type or "serial",
            status=status,
            declared_worker_count=factory.declared_worker_count or 0,
            registered_worker_count=factory.registered_worker_count or 0,
            assets_count=assets_count,
            process_stages_count=stages_count,
            shifts_count=shifts_count,
            job_desks_count=job_desks_count,
            workers_count=workers_count,
            evaluations_count=evaluations_count,
            simulation_configured=simulation_configured,
            created_at=factory.created_at.isoformat() if factory.created_at else None,
        )

    async def list_factories(
        self, limit: int = 20, offset: int = 0
    ) -> list[schemas.FactorySummary]:
        stmt = (
            select(models.Factory.factory_id)
            .order_by(models.Factory.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        factory_ids = (await self.db.execute(stmt)).scalars().all()

        summaries: list[schemas.FactorySummary] = []
        for factory_id in factory_ids:
            summary = await self.get_summary(factory_id)
            if summary is not None:
                summaries.append(summary)
        return summaries

    async def get_twin_response(
        self, factory_id: str
    ) -> schemas.FactoryDigitalTwinResponse | None:
        summary = await self.get_summary(factory_id)
        if summary is None:
            return None

        twin = await self.get_full_twin(factory_id)
        return schemas.FactoryDigitalTwinResponse(
            factory_id=factory_id,
            status=summary.status,
            summary=summary,
            digital_twin=twin,
            warnings=twin.warnings,
        )

    # ------------------------------------------------------------------
    # Input mentah untuk Tahap 5 (matriks kompatibilitas)
    # ------------------------------------------------------------------

    async def get_matrix_inputs(
        self, factory_id: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
        """
        Merakit `factory_structure` & daftar worker dalam bentuk dict mentah langsung
        dari tabel relasional, siap dipakai oleh `generate_compatibility_matrix`.
        """
        warnings: list[str] = []

        assets = (
            (await self.db.execute(select(models.Asset).where(models.Asset.factory_id == factory_id)))
            .scalars()
            .all()
        )
        job_desks = (
            (await self.db.execute(select(models.JobDesk).where(models.JobDesk.factory_id == factory_id)))
            .scalars()
            .all()
        )
        workers = (
            (await self.db.execute(select(models.Worker).where(models.Worker.factory_id == factory_id)))
            .scalars()
            .all()
        )

        asset_payloads: dict[str, Any] = {
            a.asset_id: {
                "asset_id": a.asset_id,
                "asset_name": a.asset_name,
                "category": a.category,
                "units_available": a.units_available,
                "is_automated": a.is_automated,
                "automation_level": a.automation_level or "manual",
                "environmental_factors": _environmental_factors(a.environmental_factors).model_dump(),
            }
            for a in assets
        }

        job_payloads: list[dict[str, Any]] = []
        for job in job_desks:
            if job.assigned_asset_id not in asset_payloads:
                warnings.append(
                    f"Job desk '{job.job_id}' merujuk asset_id '{job.assigned_asset_id}' "
                    f"yang tidak terdaftar; asset placeholder dipakai."
                )
                asset_payloads[job.assigned_asset_id] = {
                    "asset_id": job.assigned_asset_id,
                    "asset_name": f"Asset Tidak Dikenal ({job.assigned_asset_id})",
                    "category": "manual_station",
                    "units_available": 1,
                    "is_automated": False,
                    "automation_level": "manual",
                    "environmental_factors": _environmental_factors(None).model_dump(),
                }
            job_payloads.append(
                {
                    "job_id": job.job_id,
                    "allocation_id": job.allocation_id or job.job_id,
                    "job_title": job.job_title,
                    "stage_id": job.stage_id,
                    "assigned_asset_id": job.assigned_asset_id,
                    "assigned_worker_ids": job.assigned_worker_ids or [],
                    "shift_id": job.shift_id,
                    "headcount": job.headcount,
                    "demands": _demands(job.demands).model_dump(),
                    "qc_requirement": job.qc_requirement or "",
                    "metric_derivation_reasoning": job.metric_derivation_reasoning or "",
                }
            )

        worker_payloads: list[dict[str, Any]] = []
        for worker in workers:
            if not isinstance(worker.demographics, dict) or not worker.demographics:
                warnings.append(
                    f"Worker '{worker.worker_id}' tidak memiliki demografi lengkap; nilai default dipakai."
                )
            worker_payloads.append(
                {
                    "worker_id": worker.worker_id,
                    "name": worker.name or worker.worker_id,
                    "demographics": _demographics(worker.demographics).model_dump(),
                    "shift_context": _shift_context(worker.shift_context).model_dump(),
                    "skills": worker.skills or [],
                    "certifications": worker.certifications or [],
                    "capabilities": worker.capabilities or [],
                }
            )

        factory_structure = {
            "factory_info": {"factory_id": factory_id},
            "assets": list(asset_payloads.values()),
            "job_desks": job_payloads,
        }
        return factory_structure, worker_payloads, warnings

    # ------------------------------------------------------------------
    # Retrieval Digital Twin
    # ------------------------------------------------------------------

    async def _resolve_factory_id(self, job_id: str | int | None) -> str | None:
        """Resolve factory_id dari factory_id langsung maupun job_id audit log."""
        if not job_id:
            return None

        job_str = str(job_id).strip()

        direct = await self.db.get(models.Factory, job_str)
        if direct is not None:
            return direct.factory_id

        if job_str.isdigit():
            try:
                from app.modules.documents.models import DocumentParseJob

                stmt_job = select(DocumentParseJob).where(DocumentParseJob.id == int(job_str))
                parse_job = (await self.db.execute(stmt_job)).scalar_one_or_none()
                if parse_job:
                    if parse_job.factory_id:
                        return parse_job.factory_id
                    if isinstance(parse_job.factory_structure, dict):
                        fac_info = parse_job.factory_structure.get("factory_info", {})
                        if fac_info.get("factory_id"):
                            return str(fac_info["factory_id"])
                    return f"FAC-{parse_job.id}"
            except Exception:
                pass

        stmt_fac = select(models.Factory.factory_id).where(
            models.Factory.factory_id.like(f"%-job{job_str}")
        )
        factory_id = (await self.db.execute(stmt_fac)).scalars().first()
        return factory_id or job_str

    async def get_full_twin(self, job_id: str | int | None = None) -> schemas.DigitalTwin:
        """
        Mengambil data Digital Twin lengkap berdasarkan factory_id (atau job_id audit
        log). Bila tidak diberikan, mengambil factory yang paling baru dibuat.
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

        factory = (await self.db.execute(query)).scalars().first()

        if not factory:
            return schemas.DigitalTwin(
                factory_info=schemas.FactoryInfo(
                    factory_id=factory_id or "",
                    factory_name="",
                    process_type="serial",
                    declared_worker_count=0,
                    registered_worker_count=0,
                    layout_description="",
                ),
                warnings=[
                    f"Data Digital Twin untuk factory '{job_id}' belum tersedia."
                    if job_id
                    else "Data Digital Twin belum tersedia. Silakan inisialisasi factory terlebih dahulu."
                ],
            )

        worker_name_map = {w.worker_id: w.name for w in factory.workers}

        latest_snapshot = factory.flow_snapshots[-1] if factory.flow_snapshots else None
        factory_flow = None
        if latest_snapshot:
            snapshot_ts = latest_snapshot.snapshot_timestamp
            factory_flow = schemas.FactoryFlowRightNow(
                snapshot_timestamp=(
                    snapshot_ts.isoformat() if isinstance(snapshot_ts, datetime) else str(snapshot_ts)
                ),
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

        return schemas.DigitalTwin(
            factory_info=schemas.FactoryInfo(
                factory_id=factory.factory_id,
                factory_name=factory.factory_name,
                process_type=_literal(factory.process_type, _PROCESS_TYPES, "serial"),
                declared_worker_count=factory.declared_worker_count or 0,
                registered_worker_count=factory.registered_worker_count or 0,
                layout_description=factory.layout_description or "",
                workflow_sequence=factory.workflow_sequence or [],
                process_edges=[
                    edge
                    for edge in (_process_edge(pe) for pe in (factory.process_edges or []))
                    if edge is not None
                ],
                entry_stages=factory.entry_stages or [],
                terminal_stages=factory.terminal_stages or [],
                parallel_groups=[
                    group
                    for group in (_parallel_group(pg) for pg in (factory.parallel_groups or []))
                    if group is not None
                ],
                lanes=factory.lanes or [],
            ),
            assets=[
                schemas.Asset(
                    asset_id=a.asset_id,
                    asset_name=a.asset_name,
                    category=_literal(a.category, _ASSET_CATEGORIES, "manual_station"),
                    units_available=a.units_available or 0,
                    capacity_per_unit=_quantity(a.capacity_per_unit),
                    total_capacity=_quantity(a.total_capacity),
                    automation_level=_literal(a.automation_level, _AUTOMATION_LEVELS, "manual"),
                    is_automated=bool(a.is_automated),
                    operational_cost_per_hour=_as_float(a.operational_cost_per_hour, 0.0) or 0.0,
                    currency=a.currency or "IDR",
                    environmental_factors=_environmental_factors(a.environmental_factors),
                    metric_derivation_reasoning=a.metric_derivation_reasoning,
                )
                for a in factory.assets
            ],
            process_stages=[
                schemas.ProcessStage(
                    stage_id=s.stage_id,
                    stage_name=s.stage_name,
                    lane=s.lane or "main",
                    next_stage_id=s.next_stage_id,
                    is_terminal=bool(s.is_terminal),
                    asset_id=s.asset_id,
                    operator_task=s.operator_task or "",
                    material_input=s.material_input or [],
                    material_output=s.material_output or [],
                    material_per_batch=[_quantity(q) for q in (s.material_per_batch or [])],
                    flow_type=_literal(s.flow_type, _FLOW_TYPES, "batch"),
                    cycle_time_seconds=_as_float(s.cycle_time_seconds, 0.0) or 0.0,
                    throughput=_quantity(s.throughput),
                    throughput_per_hour=_as_float(s.throughput_per_hour),
                    automation_level=_literal(s.automation_level, _AUTOMATION_LEVELS, "manual"),
                    qc_requirement=s.qc_requirement or "",
                    metric_derivation_reasoning=s.metric_derivation_reasoning,
                )
                for s in factory.process_stages
            ],
            shifts=[
                schemas.Shift(
                    shift_id=sh.shift_id,
                    start_time=sh.start_time,
                    end_time=sh.end_time,
                    duration_hours=_as_float(sh.duration_hours, 0.0) or 0.0,
                    crosses_midnight=bool(sh.crosses_midnight),
                )
                for sh in factory.shifts
            ],
            job_desks=[
                schemas.JobDesk(
                    job_id=j.job_id,
                    allocation_id=j.allocation_id or j.job_id,
                    job_title=j.job_title,
                    stage_id=j.stage_id,
                    assigned_asset_id=j.assigned_asset_id,
                    assigned_worker_ids=j.assigned_worker_ids or [],
                    shift_id=j.shift_id,
                    headcount=j.headcount or 1,
                    demands=_demands(j.demands),
                    qc_requirement=j.qc_requirement or "",
                    metric_derivation_reasoning=j.metric_derivation_reasoning,
                )
                for j in factory.job_desks
            ],
            workers=[
                schemas.Worker(
                    worker_id=w.worker_id,
                    name=w.name or w.worker_id,
                    demographics=_demographics(w.demographics),
                    shift_context=_shift_context(w.shift_context),
                    skills=w.skills,
                    certifications=w.certifications,
                    capabilities=w.capabilities,
                )
                for w in factory.workers
            ],
            factory_flow_rightnow=factory_flow,
            llm_compatibility_and_evaluations=[
                schemas.CompatibilityEvaluation(
                    worker_id=e.worker_id,
                    job_id=e.job_id,
                    asset_id=e.asset_id,
                    evaluations=e.evaluations if isinstance(e.evaluations, dict) else {},
                    llm_reasoning=e.llm_reasoning or "",
                )
                for e in factory.evaluations
            ],
            warnings=[],
        )

    async def get_assets(self, job_id: str | int | None = None) -> list[schemas.Asset]:
        return (await self.get_full_twin(job_id)).assets

    async def get_process_stages(
        self, job_id: str | int | None = None
    ) -> list[schemas.ProcessStage]:
        return (await self.get_full_twin(job_id)).process_stages

    async def get_workers(self, job_id: str | int | None = None) -> list[schemas.Worker]:
        return (await self.get_full_twin(job_id)).workers

    async def get_job_desks(self, job_id: str | int | None = None) -> list[schemas.JobDesk]:
        return (await self.get_full_twin(job_id)).job_desks

    async def get_compatibility_matrix(
        self, job_id: str | int | None = None
    ) -> list[schemas.CompatibilityEvaluation]:
        return (await self.get_full_twin(job_id)).llm_compatibility_and_evaluations

    async def get_live_flow(
        self, job_id: str | int | None = None
    ) -> schemas.FactoryFlowRightNow | None:
        return (await self.get_full_twin(job_id)).factory_flow_rightnow

    async def save_digital_twin(self, twin: schemas.DigitalTwin) -> None:
        await self.repository.save_full_snapshot(twin)