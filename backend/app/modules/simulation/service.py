"""
Service layer modul simulation.

Backend tetap stateless untuk eksekusi simulasi -- tidak ada tick loop maupun
state antar request. Yang ditangani di sini:

1. `save_simulation_design()` -- menerima flowchart manual dari UI, memvalidasi
   seluruh relasi FK-nya di memori, lalu menyimpannya ke tabel digital twin
   (Asset/ProcessStage/Shift/JobDesk) sekaligus tabel simulasi
   (SimulationStation/Settings/WorkerThroughputMultiplier/SeedAssignment).
2. `get_simulation_config()` -- merakit parameter tick loop dari DB per factory,
   dengan fallback ke seed statis `constants.py` bila factory belum dikonfigurasi.
3. `get_simulation_overview()` -- data lengkap simulasi + graf flowchart untuk
   dirender ulang di UI.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion.models import Factory
from app.modules.documents.repository import persist_factory_structure

from . import constants as C
from .exceptions import (
    FactoryNotFoundError,
    SimulationPersistenceError,
    SimulationValidationError,
)
from .repository import SimulationRepository
from .schemas import (
    FlowchartEdge,
    FlowchartNode,
    MaterialTemplate,
    RealtimeMetrics,
    SeedAssignment,
    SimulationConfig,
    SimulationDesignRequest,
    SimulationDesignResponse,
    SimulationOverview,
    SimulationSettingsInput,
    StationInput,
)

_BURNOUT_LEVELS = {"low", "medium", "high"}


# --------------------------------------------------------------------------
# Fallback statis (dipakai bila factory belum punya konfigurasi simulasi)
# --------------------------------------------------------------------------


def _static_seed_assignments() -> list[SeedAssignment]:
    raw = [
        ("wrk-01", "job-01", "ast-01", 0.20, 0.18, 300.0, 0.010, "low", "wrk-01"),
        ("wrk-02", "job-02", "ast-02", 0.25, 0.22, 165.0, 0.014, "low", "wrk-02"),
        ("wrk-03", "job-03", "ast-03", 0.35, 0.25, 200.0, 0.018, "low", "wrk-03"),
        ("wrk-04", "job-04", "ast-04", 0.30, 0.20, 216.0, 0.015, "low", "wrk-04"),
        ("wrk-05", "job-05", "ast-05", 0.22, 0.24, 189.0, 0.016, "low", "wrk-05"),
        ("wrk-06", "job-06", "ast-06", 0.18, 0.30, 250.0, 0.008, "low", "wrk-06"),
        ("wrk-11", "job-06", "ast-06", 0.20, 0.22, 240.0, 0.010, "low", "wrk-11"),
        ("wrk-07", "job-07", "ast-07", 0.72, 0.58, 253.0, 0.030, "high", "wrk-07"),
        ("wrk-12", "job-07", "ast-07", 0.15, 0.18, 260.0, 0.009, "low", "wrk-12"),
        ("wrk-08", "job-08", "ast-08", 0.12, 0.15, 209.0, 0.012, "low", "wrk-08"),
        ("wrk-09", "job-09", "ast-09", 0.28, 0.26, 200.0, 0.011, "low", "wrk-09"),
        ("wrk-10", "job-10", "ast-10", 0.10, 0.14, 204.0, 0.010, "low", "wrk-10"),
    ]
    return [
        SeedAssignment(
            worker_id=worker_id,
            assigned_job_id=job_id,
            assigned_asset_id=asset_id,
            calculated_realtime_metrics=RealtimeMetrics(
                current_fatigue_level=fatigue,
                current_stress_level=stress,
                effective_throughput_per_hour=throughput,
                effective_error_probability=error,
                burnout_hazard_risk=risk,
                throughput_multiplier=C.WORKER_THROUGHPUT_MULTIPLIER.get(mult_key, 1.0),
            ),
        )
        for worker_id, job_id, asset_id, fatigue, stress, throughput, error, risk, mult_key in raw
    ]


def _static_fallback_config() -> SimulationConfig:
    return SimulationConfig(
        materials_by_ordinal={
            ordinal: MaterialTemplate(**tpl) for ordinal, tpl in C.MATERIAL_BY_ORDINAL.items()
        },
        step_names=C.STEP_NAMES,
        step_cost_base=C.STEP_COST_BASE,
        capacity_by_ordinal=C.CAPACITY_BY_ORDINAL,
        batch_in_by_ordinal=C.BATCH_IN_BY_ORDINAL,
        batch_out_by_ordinal=C.BATCH_OUT_BY_ORDINAL,
        cycle_ticks_by_ordinal=C.CYCLE_TICKS_BY_ORDINAL,
        step_ids_by_ordinal={
            ordinal: (f"step_07_baking" if ordinal == 7 else f"step_{ordinal:02d}")
            for ordinal in range(1, 11)
        },
        station_edges={ordinal: ([ordinal + 1] if ordinal < 10 else []) for ordinal in range(1, 11)},
        entry_ordinals=[1],
        terminal_ordinals=[10],
        ordinal_by_job_id={f"job-{ordinal:02d}": ordinal for ordinal in range(1, 11)},
        bottleneck_fill_threshold=C.BOTTLENECK_FILL_THRESHOLD,
        idle_qty_threshold=C.IDLE_QTY_THRESHOLD,
        station_1_safety_margin=C.STATION_1_SAFETY_MARGIN,
        warehouse_capacity=C.WAREHOUSE_CAPACITY,
        warehouse_feed_rate=C.WAREHOUSE_FEED_RATE,
        warehouse_step_id=C.WAREHOUSE_STEP_ID,
        worker_throughput_multiplier=C.WORKER_THROUGHPUT_MULTIPLIER,
        seed_assignments=_static_seed_assignments(),
        shift_start_minutes=C.SHIFT_START_MINUTES,
        break_start_elapsed=C.BREAK_START_ELAPSED,
        break_end_elapsed=C.BREAK_END_ELAPSED,
        shift_end_elapsed=C.SHIFT_END_ELAPSED,
        analytical_insight_summary=C.INSIGHT,
        target_output_units=C.TARGET_OUTPUT_UNITS,
        initial_batch_seq=232,
    )


# --------------------------------------------------------------------------
# Derivasi graf & stasiun dari flowchart
# --------------------------------------------------------------------------


def _normalize_edges(raw_edges: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        source = (
            edge.get("from_stage_id")
            or edge.get("fromStageId")
            or edge.get("from_stage")
            or edge.get("from")
            or edge.get("source")
        )
        target = (
            edge.get("to_stage_id")
            or edge.get("toStageId")
            or edge.get("to_stage")
            or edge.get("to")
            or edge.get("target")
        )
        if source and target:
            normalized.append({"from_stage_id": str(source), "to_stage_id": str(target)})
    return normalized


def _topological_order(stage_ids: list[str], edges: list[dict[str, str]]) -> list[str]:
    indegree = {stage_id: 0 for stage_id in stage_ids}
    adjacency: dict[str, list[str]] = {stage_id: [] for stage_id in stage_ids}

    for edge in edges:
        source, target = edge["from_stage_id"], edge["to_stage_id"]
        if source not in adjacency or target not in indegree:
            continue
        adjacency[source].append(target)
        indegree[target] += 1

    queue = deque([sid for sid in stage_ids if indegree[sid] == 0])
    ordered: list[str] = []

    while queue:
        current = queue.popleft()
        ordered.append(current)
        for neighbour in adjacency[current]:
            indegree[neighbour] -= 1
            if indegree[neighbour] == 0:
                queue.append(neighbour)

    if len(ordered) != len(stage_ids):
        ordered += [sid for sid in stage_ids if sid not in ordered]

    return ordered


def _derive_graph(
    payload: SimulationDesignRequest, warnings: list[str]
) -> dict[str, Any]:
    stage_ids = [stage.stage_id for stage in payload.process_stages]

    edges = _normalize_edges(payload.factory_info.process_edges)
    seen = {(e["from_stage_id"], e["to_stage_id"]) for e in edges}
    for stage in payload.process_stages:
        if stage.next_stage_id and (stage.stage_id, stage.next_stage_id) not in seen:
            edges.append(
                {"from_stage_id": stage.stage_id, "to_stage_id": stage.next_stage_id}
            )
            seen.add((stage.stage_id, stage.next_stage_id))

    workflow_sequence = payload.factory_info.workflow_sequence or _topological_order(
        stage_ids, edges
    )

    targets = {e["to_stage_id"] for e in edges}
    sources = {e["from_stage_id"] for e in edges}

    entry_stages = payload.factory_info.entry_stages or [
        sid for sid in stage_ids if sid not in targets
    ]
    terminal_stages = payload.factory_info.terminal_stages or [
        stage.stage_id
        for stage in payload.process_stages
        if stage.is_terminal or stage.stage_id not in sources
    ]

    lanes = list(payload.factory_info.lanes)
    for stage in payload.process_stages:
        if stage.lane and stage.lane not in lanes:
            lanes.append(stage.lane)
            warnings.append(
                f"Lane '{stage.lane}' dipakai stage '{stage.stage_id}' namun belum "
                f"terdaftar pada factoryInfo.lanes; ditambahkan otomatis."
            )

    return {
        "workflow_sequence": workflow_sequence,
        "process_edges": edges,
        "entry_stages": entry_stages,
        "terminal_stages": terminal_stages,
        "lanes": lanes,
    }


def _derive_stations(
    payload: SimulationDesignRequest, workflow_sequence: list[str]
) -> list[StationInput]:
    stage_map = {stage.stage_id: stage for stage in payload.process_stages}
    asset_map = {asset.asset_id: asset for asset in payload.assets}

    stations: list[StationInput] = []
    ordinal = 0
    for stage_id in workflow_sequence:
        stage = stage_map.get(stage_id)
        if stage is None:
            continue
        ordinal += 1

        capacity = stage.throughput.value or stage.throughput_per_hour or 0.0
        capacity = float(capacity) if capacity and capacity > 0 else 1.0

        asset = asset_map.get(stage.asset_id)
        cost_base = int(asset.operational_cost_per_hour) if asset else 0

        material_name = stage.material_output[0] if stage.material_output else stage.stage_name
        material_unit = stage.throughput.unit or "pcs"

        stations.append(
            StationInput(
                ordinal=ordinal,
                stage_id=stage.stage_id,
                step_name=stage.stage_name,
                material_name=material_name,
                material_unit=material_unit,
                step_cost_base=max(0, cost_base),
                capacity=capacity,
                batch_in=capacity,
                batch_out=capacity,
                cycle_ticks=max(1, round(stage.cycle_time_seconds / 60)),
            )
        )
    return stations


def _default_metrics(multiplier: float) -> dict[str, Any]:
    return {
        "current_fatigue_level": 0.0,
        "current_stress_level": 0.0,
        "effective_throughput_per_hour": 0.0,
        "effective_error_probability": 0.0,
        "burnout_hazard_risk": "low",
        "throughput_multiplier": multiplier,
    }


# --------------------------------------------------------------------------
# Validasi silang FK flowchart (di memori, sebelum menyentuh DB)
# --------------------------------------------------------------------------


def _validate_design(
    payload: SimulationDesignRequest, known_worker_ids: set[str]
) -> list[str]:
    errors: list[str] = []

    asset_ids = [asset.asset_id for asset in payload.assets]
    stage_ids = [stage.stage_id for stage in payload.process_stages]
    shift_ids = [shift.shift_id for shift in payload.shifts]
    job_ids = [job.job_id for job in payload.job_desks]

    for label, values in (
        ("assets.assetId", asset_ids),
        ("processStages.stageId", stage_ids),
        ("shifts.shiftId", shift_ids),
        ("jobDesks.jobId", job_ids),
    ):
        duplicates = sorted({v for v in values if values.count(v) > 1})
        if duplicates:
            errors.append(f"{label} duplikat pada payload: {', '.join(duplicates)}")

    asset_set, stage_set = set(asset_ids), set(stage_ids)
    shift_set, job_set = set(shift_ids), set(job_ids)

    if not stage_ids:
        errors.append("processStages tidak boleh kosong; flowchart minimal memiliki satu stage.")
    if not job_ids:
        errors.append("jobDesks tidak boleh kosong; matriks kompatibilitas butuh minimal satu job.")

    for stage in payload.process_stages:
        if stage.asset_id not in asset_set:
            errors.append(
                f"Stage '{stage.stage_id}' merujuk assetId '{stage.asset_id}' "
                f"yang tidak ada pada daftar assets."
            )
        if stage.next_stage_id and stage.next_stage_id not in stage_set:
            errors.append(
                f"Stage '{stage.stage_id}' memiliki nextStageId '{stage.next_stage_id}' "
                f"yang tidak ada pada daftar processStages."
            )

    for job in payload.job_desks:
        if job.stage_id not in stage_set:
            errors.append(
                f"Job desk '{job.job_id}' merujuk stageId '{job.stage_id}' yang tidak ada."
            )
        if job.assigned_asset_id not in asset_set:
            errors.append(
                f"Job desk '{job.job_id}' merujuk assignedAssetId "
                f"'{job.assigned_asset_id}' yang tidak ada."
            )
        if job.shift_id not in shift_set:
            errors.append(
                f"Job desk '{job.job_id}' merujuk shiftId '{job.shift_id}' yang tidak ada."
            )
        for worker_id in job.assigned_worker_ids:
            if worker_id not in known_worker_ids:
                errors.append(
                    f"Job desk '{job.job_id}' menugaskan workerId '{worker_id}' yang belum "
                    f"terdaftar pada factory ini. Jalankan Step 4 (ekstraksi ZIP CV) dahulu."
                )

    for edge in _normalize_edges(payload.factory_info.process_edges):
        if edge["from_stage_id"] not in stage_set or edge["to_stage_id"] not in stage_set:
            errors.append(f"processEdges merujuk stageId tidak dikenal: {edge}")

    for field_name, values in (
        ("workflowSequence", payload.factory_info.workflow_sequence),
        ("entryStages", payload.factory_info.entry_stages),
        ("terminalStages", payload.factory_info.terminal_stages),
    ):
        unknown = [v for v in values if v not in stage_set]
        if unknown:
            errors.append(f"{field_name} berisi stageId tidak dikenal: {', '.join(unknown)}")

    ordinals = [station.ordinal for station in payload.stations]
    duplicate_ordinals = sorted({o for o in ordinals if ordinals.count(o) > 1})
    if duplicate_ordinals:
        errors.append(
            f"stations.ordinal duplikat: {', '.join(str(o) for o in duplicate_ordinals)}"
        )

    station_stage_ids = [s.stage_id for s in payload.stations if s.stage_id]
    duplicate_station_stages = sorted(
        {s for s in station_stage_ids if station_stage_ids.count(s) > 1}
    )
    if duplicate_station_stages:
        errors.append(
            f"stations.stageId dipakai lebih dari satu stasiun: "
            f"{', '.join(duplicate_station_stages)}"
        )
    for station in payload.stations:
        if station.stage_id and station.stage_id not in stage_set:
            errors.append(
                f"Station ordinal {station.ordinal} merujuk stageId "
                f"'{station.stage_id}' yang tidak ada pada daftar processStages."
            )

    seen_workers: set[str] = set()
    for assignment in payload.seed_assignments:
        if assignment.worker_id not in known_worker_ids:
            errors.append(
                f"seedAssignments merujuk workerId '{assignment.worker_id}' yang belum terdaftar."
            )
        if assignment.assigned_job_id not in job_set:
            errors.append(
                f"seedAssignments worker '{assignment.worker_id}' merujuk jobId "
                f"'{assignment.assigned_job_id}' yang tidak ada."
            )
        if assignment.assigned_asset_id not in asset_set:
            errors.append(
                f"seedAssignments worker '{assignment.worker_id}' merujuk assetId "
                f"'{assignment.assigned_asset_id}' yang tidak ada."
            )
        if assignment.worker_id in seen_workers:
            errors.append(
                f"seedAssignments duplikat untuk worker '{assignment.worker_id}' "
                f"(satu worker hanya boleh punya satu assignment per factory)."
            )
        seen_workers.add(assignment.worker_id)

    for multiplier in payload.worker_multipliers:
        if multiplier.worker_id not in known_worker_ids:
            errors.append(
                f"workerMultipliers merujuk workerId '{multiplier.worker_id}' yang belum terdaftar."
            )

    return errors


# --------------------------------------------------------------------------
# Penyimpanan flowchart manual
# --------------------------------------------------------------------------


async def save_simulation_design(
    db: AsyncSession, factory_id: str, payload: SimulationDesignRequest
) -> SimulationDesignResponse:
    repository = SimulationRepository(db)

    factory = await db.get(Factory, factory_id)
    if factory is None:
        raise FactoryNotFoundError(factory_id)

    known_worker_ids = await repository.load_worker_ids(factory_id)

    errors = _validate_design(payload, known_worker_ids)
    if errors:
        raise SimulationValidationError(
            f"Ditemukan {len(errors)} kesalahan pada konfigurasi flowchart.", errors
        )

    warnings: list[str] = []
    graph = _derive_graph(payload, warnings)

    stations = payload.stations or _derive_stations(payload, graph["workflow_sequence"])
    if not payload.stations:
        warnings.append(
            "stations tidak dikirim; parameter stasiun diturunkan otomatis dari processStages."
        )

    seed_assignments = list(payload.seed_assignments)
    if not seed_assignments:
        assigned: dict[str, Any] = {}
        for job in payload.job_desks:
            for worker_id in job.assigned_worker_ids:
                if worker_id in assigned:
                    warnings.append(
                        f"Worker '{worker_id}' ditugaskan pada lebih dari satu job; "
                        f"assignment pertama ('{assigned[worker_id]['assigned_job_id']}') dipakai."
                    )
                    continue
                assigned[worker_id] = {
                    "worker_id": worker_id,
                    "assigned_job_id": job.job_id,
                    "assigned_asset_id": job.assigned_asset_id,
                    "realtime_metrics": None,
                }
        seed_rows = list(assigned.values())
    else:
        seed_rows = [
            {
                "worker_id": a.worker_id,
                "assigned_job_id": a.assigned_job_id,
                "assigned_asset_id": a.assigned_asset_id,
                "realtime_metrics": a.realtime_metrics,
            }
            for a in seed_assignments
        ]

    multipliers = {m.worker_id: m.multiplier for m in payload.worker_multipliers}
    for row in seed_rows:
        multipliers.setdefault(row["worker_id"], 1.0)

    settings = payload.settings or SimulationSettingsInput()

    twin = {
        "factory_info": {
            "factory_id": factory_id,
            "factory_name": factory.factory_name,
            "process_type": payload.factory_info.process_type,
            "declared_worker_count": factory.declared_worker_count,
            "registered_worker_count": len(known_worker_ids),
            "layout_description": (
                payload.factory_info.layout_description
                if payload.factory_info.layout_description is not None
                else factory.layout_description
            ),
            **graph,
            "parallel_groups": payload.factory_info.parallel_groups,
        },
        "assets": [
            {
                **asset.model_dump(),
                "capacity_per_unit": asset.capacity_per_unit.normalized(),
                "total_capacity": asset.total_capacity.normalized(),
                "environmental_factors": asset.environmental_factors.model_dump(),
            }
            for asset in payload.assets
        ],
        "process_stages": [
            {
                **stage.model_dump(),
                "throughput": stage.throughput.normalized(),
                "material_per_batch": [q.normalized() for q in stage.material_per_batch],
            }
            for stage in payload.process_stages
        ],
        "shifts": [shift.normalized() for shift in payload.shifts],
        "job_desks": [
            {
                **job.model_dump(),
                "allocation_id": job.allocation_id or job.job_id,
                "demands": job.demands.model_dump(),
            }
            for job in payload.job_desks
        ],
    }

    try:
        if payload.prune_missing:
            await repository.prune_structure(
                factory_id,
                keep_asset_ids={a.asset_id for a in payload.assets},
                keep_stage_ids={s.stage_id for s in payload.process_stages},
                keep_shift_ids={s.shift_id for s in payload.shifts},
                keep_job_ids={j.job_id for j in payload.job_desks},
            )

        await persist_factory_structure(db, twin, warnings)

        stations_saved = await repository.replace_stations(
            factory_id, [station.model_dump() for station in stations]
        )
        await repository.upsert_settings(factory_id, settings.model_dump())
        multipliers_saved = await repository.replace_worker_multipliers(
            factory_id, multipliers
        )
        seed_saved = await repository.replace_seed_assignments(
            factory_id,
            [
                {
                    "worker_id": row["worker_id"],
                    "assigned_job_id": row["assigned_job_id"],
                    "assigned_asset_id": row["assigned_asset_id"],
                    "realtime_metrics_cache": row["realtime_metrics"]
                    or _default_metrics(multipliers.get(row["worker_id"], 1.0)),
                }
                for row in seed_rows
            ],
        )

        factory.registered_worker_count = len(known_worker_ids)
        await db.commit()
    except SQLAlchemyError as error:
        await db.rollback()
        raise SimulationPersistenceError(
            "Gagal menyimpan konfigurasi simulasi ke database.", [str(error)]
        ) from error

    return SimulationDesignResponse(
        factory_id=factory_id,
        assets_saved=len(payload.assets),
        process_stages_saved=len(payload.process_stages),
        shifts_saved=len(payload.shifts),
        job_desks_saved=len(payload.job_desks),
        stations_saved=stations_saved,
        worker_multipliers_saved=multipliers_saved,
        seed_assignments_saved=seed_saved,
        warnings=warnings,
    )


# --------------------------------------------------------------------------
# Pembacaan konfigurasi & overview
# --------------------------------------------------------------------------


def _build_station_topology(
    factory: Factory | None,
    stations: list[Any],
    job_desks: list[Any],
) -> dict[str, Any]:
    ordinals = [station.ordinal for station in stations]
    ordinal_by_stage = {
        station.stage_id: station.ordinal for station in stations if station.stage_id
    }

    edges: dict[int, list[int]] = {ordinal: [] for ordinal in ordinals}
    raw_edges = (factory.process_edges or []) if factory is not None else []

    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        source = ordinal_by_stage.get(raw.get("from_stage_id"))
        target = ordinal_by_stage.get(raw.get("to_stage_id"))
        if source is None or target is None or source == target:
            continue
        if target not in edges[source]:
            edges[source].append(target)

    has_any_edge = any(targets for targets in edges.values())
    if not has_any_edge and len(ordinals) > 1:
        ordered = sorted(ordinals)
        for current, following in zip(ordered, ordered[1:]):
            edges[current] = [following]

    reachable = {target for targets in edges.values() for target in targets}

    declared_entries = [
        ordinal_by_stage[stage_id]
        for stage_id in ((factory.entry_stages or []) if factory is not None else [])
        if stage_id in ordinal_by_stage
    ]
    declared_terminals = [
        ordinal_by_stage[stage_id]
        for stage_id in ((factory.terminal_stages or []) if factory is not None else [])
        if stage_id in ordinal_by_stage
    ]

    entry_ordinals = declared_entries or [o for o in ordinals if o not in reachable]
    terminal_ordinals = declared_terminals or [o for o in ordinals if not edges[o]]

    if not entry_ordinals and ordinals:
        entry_ordinals = [min(ordinals)]
    if not terminal_ordinals and ordinals:
        terminal_ordinals = [max(ordinals)]

    ordinal_by_job_id = {
        job.job_id: ordinal_by_stage[job.stage_id]
        for job in job_desks
        if job.stage_id in ordinal_by_stage
    }

    return {
        "step_ids_by_ordinal": {
            station.ordinal: (station.stage_id or f"step_{station.ordinal:02d}")
            for station in stations
        },
        "station_edges": edges,
        "entry_ordinals": sorted(set(entry_ordinals)),
        "terminal_ordinals": sorted(set(terminal_ordinals)),
        "ordinal_by_job_id": ordinal_by_job_id,
    }


async def _build_config_from_db(
    repository: SimulationRepository, factory_id: str
) -> SimulationConfig | None:
    stations = await repository.load_stations(factory_id)
    if not stations:
        return None

    factory = await repository.load_factory(factory_id)
    job_desks = await repository.load_job_desks(factory_id)
    topology = _build_station_topology(factory, stations, job_desks)

    settings = await repository.load_settings(factory_id)
    multipliers = await repository.load_worker_multipliers(factory_id)
    assignments = await repository.load_seed_assignments(factory_id)

    seed_assignments: list[SeedAssignment] = []
    for row in assignments:
        multiplier = multipliers.get(row.worker_id, 1.0)
        cache = row.realtime_metrics_cache or _default_metrics(multiplier)
        risk = str(cache.get("burnout_hazard_risk", "low")).lower()
        seed_assignments.append(
            SeedAssignment(
                worker_id=row.worker_id,
                assigned_job_id=row.assigned_job_id,
                assigned_asset_id=row.assigned_asset_id,
                calculated_realtime_metrics=RealtimeMetrics(
                    current_fatigue_level=float(cache.get("current_fatigue_level", 0.0)),
                    current_stress_level=float(cache.get("current_stress_level", 0.0)),
                    effective_throughput_per_hour=float(
                        cache.get("effective_throughput_per_hour", 0.0)
                    ),
                    effective_error_probability=float(
                        cache.get("effective_error_probability", 0.0)
                    ),
                    burnout_hazard_risk=risk if risk in _BURNOUT_LEVELS else "high",
                    throughput_multiplier=float(
                        cache.get("throughput_multiplier", multiplier)
                    ),
                ),
            )
        )

    defaults = SimulationSettingsInput()
    resolved = settings or defaults

    return SimulationConfig(
        materials_by_ordinal={
            s.ordinal: MaterialTemplate(name=s.material_name, unit=s.material_unit)
            for s in stations
        },
        step_names={s.ordinal: s.step_name for s in stations},
        step_cost_base={s.ordinal: s.step_cost_base for s in stations},
        capacity_by_ordinal={s.ordinal: s.capacity for s in stations},
        batch_in_by_ordinal={s.ordinal: s.batch_in for s in stations},
        batch_out_by_ordinal={s.ordinal: s.batch_out for s in stations},
        cycle_ticks_by_ordinal={s.ordinal: s.cycle_ticks for s in stations},
        **topology,
        bottleneck_fill_threshold=resolved.bottleneck_fill_threshold,
        idle_qty_threshold=resolved.idle_qty_threshold,
        station_1_safety_margin=resolved.station_1_safety_margin,
        warehouse_capacity=resolved.warehouse_capacity,
        warehouse_feed_rate=resolved.warehouse_feed_rate,
        warehouse_step_id=resolved.warehouse_step_id,
        worker_throughput_multiplier=multipliers,
        seed_assignments=seed_assignments,
        shift_start_minutes=resolved.shift_start_minutes,
        break_start_elapsed=resolved.break_start_elapsed,
        break_end_elapsed=resolved.break_end_elapsed,
        shift_end_elapsed=resolved.shift_end_elapsed,
        analytical_insight_summary=resolved.analytical_insight_summary,
        target_output_units=resolved.target_output_units,
        initial_batch_seq=resolved.initial_batch_seq,
    )


async def get_simulation_config(
    db: AsyncSession | None = None, factory_id: str | None = None
) -> SimulationConfig:
    if db is None:
        return _static_fallback_config()

    repository = SimulationRepository(db)
    resolved_id = factory_id or await repository.latest_configured_factory_id()
    if not resolved_id:
        return _static_fallback_config()

    config = await _build_config_from_db(repository, resolved_id)
    return config or _static_fallback_config()


async def get_simulation_overview(
    db: AsyncSession, factory_id: str
) -> SimulationOverview:
    repository = SimulationRepository(db)
    factory, stages, jobs = await repository.load_structure(factory_id)
    if factory is None:
        raise FactoryNotFoundError(factory_id)

    config = await _build_config_from_db(repository, factory_id)
    warnings: list[str] = []
    if config is None:
        warnings.append(
            "Factory ini belum memiliki konfigurasi simulasi; konfigurasi seed statis dikembalikan."
        )
        config = _static_fallback_config()

    stations = await repository.load_stations(factory_id)
    ordinal_by_stage = {
        station.stage_id: station.ordinal for station in stations if station.stage_id
    }

    jobs_by_stage: dict[str, list[Any]] = {}
    for job in jobs:
        jobs_by_stage.setdefault(job.stage_id, []).append(job)

    nodes = [
        FlowchartNode(
            stage_id=stage.stage_id,
            stage_name=stage.stage_name,
            lane=stage.lane,
            ordinal=ordinal_by_stage.get(stage.stage_id),
            asset_id=stage.asset_id,
            next_stage_id=stage.next_stage_id,
            is_terminal=stage.is_terminal,
            job_ids=[job.job_id for job in jobs_by_stage.get(stage.stage_id, [])],
            worker_ids=[
                worker_id
                for job in jobs_by_stage.get(stage.stage_id, [])
                for worker_id in (job.assigned_worker_ids or [])
            ],
        )
        for stage in stages
    ]

    edges = [
        FlowchartEdge(from_stage_id=edge["from_stage_id"], to_stage_id=edge["to_stage_id"])
        for edge in _normalize_edges(factory.process_edges or [])
    ]

    settings = await repository.load_settings(factory_id)

    return SimulationOverview(
        factory_id=factory_id,
        factory_name=factory.factory_name,
        is_configured=bool(stations),
        process_type=factory.process_type or "serial",
        workflow_sequence=factory.workflow_sequence or [],
        entry_stages=factory.entry_stages or [],
        terminal_stages=factory.terminal_stages or [],
        lanes=factory.lanes or [],
        nodes=nodes,
        edges=edges,
        config=config,
        updated_at=settings.updated_at.isoformat() if settings and settings.updated_at else None,
        warnings=warnings,
    )