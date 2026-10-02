from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.digital_twin_ingestion import schemas as twin_schemas
from app.modules.digital_twin_ingestion.service import DigitalTwinService
from app.services.snapshot_builder import EVALUATION_BOUNDS, EVALUATION_FIELDS, STATUS_ORDER

DEFAULT_STATION_RATE = 60.0
DEFAULT_NOISE_DB = 60.0
DEFAULT_DEMANDS = {
    "required_cognitive_focus": 0.5,
    "physical_demand_level": "medium",
    "task_complexity": 0.5,
    "error_severity": "moderate",
}
LEVELS = {"low", "medium", "high"}
SEVERITIES = {"low", "moderate", "high", "critical"}
BROWSER_STATUS = {
    "active": "processing",
    "rework": "processing",
    "handover": "processing",
    "off_shift": "processing",
    "idle": "idle_waiting_input",
    "on_break": "on_break",
}
SUMMARY_KEYS = (
    "simulation_summary",
    "system_bottlenecks",
    "analytical_insight_summary",
    "shift_info",
)


class RlInputError(ValueError):
    """Raised when a digital twin cannot be turned into a valid RL snapshot."""


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    """Convert a value to float and clamp it, falling back to a default when missing."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _unwrap(state: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Accept either a LiveSimulationState or a {live_simulation_state: ...} wrapper."""
    if not state:
        return None
    return state.get("live_simulation_state", state)


def _ordered_stages(twin: twin_schemas.DigitalTwin) -> list[twin_schemas.ProcessStage]:
    """Order stages by the factory workflow sequence, appending any stage it omits."""
    by_id = {stage.stage_id: stage for stage in twin.process_stages}
    ordered = [by_id[stage_id] for stage_id in twin.factory_info.workflow_sequence if stage_id in by_id]
    seen = {stage.stage_id for stage in ordered}
    ordered.extend(stage for stage in twin.process_stages if stage.stage_id not in seen)
    return ordered


def _stage_rate(stage: twin_schemas.ProcessStage, asset: Optional[twin_schemas.Asset]) -> float:
    """Resolve the nominal items-per-hour rate of a stage from the best available field."""
    candidates = [
        stage.throughput_per_hour,
        stage.throughput.value if stage.throughput else None,
        3600.0 / stage.cycle_time_seconds if stage.cycle_time_seconds else None,
        asset.total_capacity.value if asset and asset.total_capacity else None,
    ]
    for candidate in candidates:
        if candidate is not None and candidate > 0:
            return float(candidate)
    return DEFAULT_STATION_RATE


def _asset_entry(stage: twin_schemas.ProcessStage, asset: Optional[twin_schemas.Asset]) -> dict[str, Any]:
    """Build the per-station asset record expected by SnapshotBuilder."""
    units = max(1, int(asset.units_available)) if asset else 1
    environment = asset.environmental_factors if asset else None
    vibration = environment.vibration_hazard_level if environment else "low"
    return {
        "asset_id": stage.asset_id or f"asset-{stage.stage_id}",
        "workflow_step": stage.stage_id,
        "base_throughput_capacity": _stage_rate(stage, asset) / units,
        "operational_cost_per_hour": (float(asset.operational_cost_per_hour) if asset else 0.0) / units,
        "units_available": units,
        "is_automated": bool(
            (asset.is_automated if asset else False) or stage.automation_level == "automated"
        ),
        "environmental_factors": {
            "noise_level_db": _clamp(
                environment.noise_level_db if environment else None, 0.0, 140.0, DEFAULT_NOISE_DB
            ),
            "vibration_hazard_level": vibration if vibration in LEVELS else "low",
            "physical_strain_index": _clamp(
                environment.physical_strain_index if environment else None, 0.0, 1.0, 0.3
            ),
        },
    }


def _demands(job: twin_schemas.JobDesk) -> dict[str, Any]:
    """Normalize job demands into the value ranges SnapshotBuilder indexes into."""
    demands = job.demands
    physical = demands.physical_demand_level
    severity = demands.error_severity
    return {
        "required_cognitive_focus": _clamp(demands.required_cognitive_focus, 0.0, 1.0, 0.5),
        "physical_demand_level": physical if physical in LEVELS else "medium",
        "task_complexity": _clamp(demands.task_complexity, 0.0, 1.0, 0.5),
        "error_severity": severity if severity in SEVERITIES else "moderate",
    }


def _worker_entry(worker: twin_schemas.Worker) -> dict[str, Any]:
    """Build the worker record expected by SnapshotBuilder with bounded demographics."""
    demographics = worker.demographics
    shift = worker.shift_context
    return {
        "worker_id": worker.worker_id,
        "name": worker.name,
        "demographics": {
            "age": _clamp(demographics.age, 16.0, 75.0, 30.0),
            "years_of_experience": _clamp(demographics.years_of_experience, 0.0, 40.0, 1.0),
            "baseline_physical_stamina": _clamp(demographics.baseline_physical_stamina, 0.0, 1.0, 0.6),
            "cognitive_resilience": _clamp(demographics.cognitive_resilience, 0.0, 1.0, 0.6),
        },
        "shift_context": {
            "hours_worked_today": _clamp(shift.hours_worked_today, 0.0, 12.0, 0.0),
            "consecutive_shifts": _clamp(shift.consecutive_shifts, 0.0, 7.0, 1.0),
        },
    }


def _evaluation_values(record: twin_schemas.CompatibilityEvaluation) -> Optional[dict[str, float]]:
    """Return all five evaluation fields clamped to their bounds, or None if any is missing."""
    raw = record.evaluations
    if not isinstance(raw, dict):
        raw = raw.model_dump()
    values = {}
    for name in EVALUATION_FIELDS:
        value = raw.get(name)
        if value is None:
            return None
        low, high = EVALUATION_BOUNDS[name]
        values[name] = _clamp(value, low, high, low)
    return values


def _runtime_positions(
    runtime: list[dict[str, Any]],
    job_stage: dict[str, str],
    stage_ids: set[str],
    worker_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Read worker positions and statuses from the browser simulation runtime."""
    positions = {}
    for entry in runtime:
        worker_id = entry.get("worker_id")
        if worker_id not in worker_ids:
            continue
        stage_id = job_stage.get(entry.get("assigned_job_id") or "")
        if stage_id is None and entry.get("assigned_step_id") in stage_ids:
            stage_id = entry["assigned_step_id"]
        if stage_id is None:
            continue
        positions[worker_id] = {
            "stage_id": stage_id,
            "status": BROWSER_STATUS.get(entry.get("state", ""), "processing"),
        }
    return positions


def _design_positions(
    twin: twin_schemas.DigitalTwin, stage_ids: set[str], worker_ids: set[str]
) -> dict[str, dict[str, Any]]:
    """Read worker positions from job desk assignments, then the latest flow snapshot."""
    positions: dict[str, dict[str, Any]] = {}
    for job in twin.job_desks:
        if job.stage_id not in stage_ids:
            continue
        for worker_id in job.assigned_worker_ids:
            if worker_id in worker_ids and worker_id not in positions:
                positions[worker_id] = {"stage_id": job.stage_id, "status": "processing"}

    flow = twin.factory_flow_rightnow
    for position in flow.staff_current_positions if flow else []:
        if position.worker_id in worker_ids and position.worker_id not in positions:
            if position.current_station in stage_ids:
                status = position.activity_status
                positions[position.worker_id] = {
                    "stage_id": position.current_station,
                    "status": status if status in STATUS_ORDER else "processing",
                }
    return positions


def _speed(entry: Optional[dict[str, Any]]) -> Optional[float]:
    """Return a positive worker speed factor from a runtime entry, if one is available."""
    if not entry:
        return None
    speed = entry.get("speed_factor")
    if isinstance(speed, (int, float)) and speed > 0:
        return float(speed)
    compatibility = entry.get("compatibility_score")
    if isinstance(compatibility, (int, float)):
        return 0.55 + 0.65 * float(compatibility)
    return None


def _simulation_state(
    end_runtime: list[dict[str, Any]],
    working_runtime: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
    station_capacity: dict[str, float],
    job_by_stage: dict[str, str],
) -> dict[str, Any]:
    """Convert browser worker metrics into SnapshotBuilder realtime metrics per worker."""
    end_by_worker = {entry.get("worker_id"): entry for entry in end_runtime}
    working_by_worker = {entry.get("worker_id"): entry for entry in working_runtime}

    speeds_by_stage: dict[str, list[float]] = {}
    for worker_id, position in positions.items():
        speed = _speed(working_by_worker.get(worker_id)) or _speed(end_by_worker.get(worker_id))
        speeds_by_stage.setdefault(position["stage_id"], []).append(speed if speed else 1.0)

    stage_rate = {
        stage_id: station_capacity[stage_id]
        * max(0.15, min(1.25, sum(speeds) / len(speeds)))
        for stage_id, speeds in speeds_by_stage.items()
    }

    assignments = []
    for worker_id, position in positions.items():
        entry = end_by_worker.get(worker_id)
        if not entry:
            continue
        metrics = entry.get("metrics") or {}
        burnout = metrics.get("burnout_hazard_risk", "low")
        assignments.append(
            {
                "worker_id": worker_id,
                "assigned_job_id": job_by_stage.get(position["stage_id"], ""),
                "calculated_realtime_metrics": {
                    "current_fatigue_level": _clamp(metrics.get("current_fatigue_level"), 0.0, 1.0, 0.0),
                    "current_stress_level": _clamp(metrics.get("current_stress_level"), 0.0, 1.0, 0.0),
                    "effective_error_probability": _clamp(
                        metrics.get("effective_error_probability"), 0.0, 1.0, 0.0
                    ),
                    "burnout_hazard_risk": burnout if burnout in LEVELS else "high",
                    "effective_throughput_per_hour": stage_rate[position["stage_id"]],
                },
            }
        )
    return {"live_simulation_state": {"current_assignments": assignments}}


def build_rl_inputs(
    twin: twin_schemas.DigitalTwin,
    end_state: Optional[dict[str, Any]] = None,
    working_state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Map a digital twin plus an optional browser simulation run onto SnapshotBuilder inputs.

    Returns a dict with factory_md, worker_md, init_state, simulation_state (or None) and
    simulation_summary (or None). Raises RlInputError when the twin has no usable stations
    or no positioned workers.
    """
    stages = _ordered_stages(twin)
    if not stages:
        raise RlInputError("Digital twin belum memiliki process stage.")

    stage_ids = [stage.stage_id for stage in stages]
    stage_set = set(stage_ids)
    assets_by_id = {asset.asset_id: asset for asset in twin.assets}
    asset_entries = [_asset_entry(stage, assets_by_id.get(stage.asset_id)) for stage in stages]
    station_capacity = {
        entry["workflow_step"]: entry["base_throughput_capacity"] * entry["units_available"]
        for entry in asset_entries
    }

    jobs = []
    job_stage: dict[str, str] = {}
    job_by_stage: dict[str, str] = {}
    for job in twin.job_desks:
        if job.stage_id not in stage_set:
            continue
        jobs.append({"job_id": job.job_id, "workflow_step": job.stage_id, "demands": _demands(job)})
        job_stage[job.job_id] = job.stage_id
        job_by_stage.setdefault(job.stage_id, job.job_id)
    for stage_id in stage_ids:
        if stage_id not in job_by_stage:
            job_id = f"auto-{stage_id}"
            jobs.append({"job_id": job_id, "workflow_step": stage_id, "demands": dict(DEFAULT_DEMANDS)})
            job_stage[job_id] = stage_id
            job_by_stage[stage_id] = job_id

    workers_by_id = {worker.worker_id: worker for worker in twin.workers}
    worker_ids = set(workers_by_id)
    end = _unwrap(end_state)
    working = _unwrap(working_state)
    end_runtime = (end or {}).get("worker_runtime") or []
    working_runtime = (working or {}).get("worker_runtime") or []

    positions = _runtime_positions(end_runtime, job_stage, stage_set, worker_ids)
    if not positions:
        positions = _design_positions(twin, stage_set, worker_ids)
    if not positions:
        raise RlInputError("Tidak ada pekerja yang ditempatkan pada stasiun mana pun.")

    selected = [workers_by_id[worker_id] for worker_id in workers_by_id if worker_id in positions]

    evaluations = []
    for record in twin.llm_compatibility_and_evaluations:
        if record.worker_id not in positions or record.job_id not in job_stage:
            continue
        values = _evaluation_values(record)
        if values is not None:
            evaluations.append(
                {"worker_id": record.worker_id, "job_id": record.job_id, "evaluations": values}
            )

    factory_md = {
        "factory_info": {
            "factory_id": twin.factory_info.factory_id,
            "factory_name": twin.factory_info.factory_name,
            "workflow_sequence": stage_ids,
        },
        "assets": asset_entries,
        "job_descriptions": jobs,
    }
    init_state = {
        "factory_flow_rightnow": {
            "staff_current_positions": [
                {
                    "worker_id": worker.worker_id,
                    "name": worker.name,
                    "current_stage_id": positions[worker.worker_id]["stage_id"],
                    "activity_status": positions[worker.worker_id]["status"],
                }
                for worker in selected
            ]
        },
        "llm_compatibility_and_evaluations": evaluations,
    }

    simulation_state = None
    simulation_summary = None
    if end_runtime:
        simulation_state = _simulation_state(
            end_runtime, working_runtime, positions, station_capacity, job_by_stage
        )
        simulation_summary = {key: end.get(key) for key in SUMMARY_KEYS if key in end}
        simulation_summary["worker_end_metrics"] = [
            {
                "worker_id": entry.get("worker_id"),
                "worker_name": entry.get("worker_name"),
                "assigned_step_id": entry.get("assigned_step_id"),
                "metrics": entry.get("metrics"),
            }
            for entry in end_runtime
        ]

    return {
        "factory_md": factory_md,
        "worker_md": {"workers": [_worker_entry(worker) for worker in selected]},
        "init_state": init_state,
        "simulation_state": simulation_state,
        "simulation_summary": simulation_summary,
    }


async def load_rl_inputs(
    db: AsyncSession,
    factory_id: str,
    end_state: Optional[dict[str, Any]] = None,
    working_state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Load the digital twin of a factory from the database and map it onto RL inputs."""
    service = DigitalTwinService(db)
    if await service.get_factory(factory_id) is None:
        raise LookupError(f"Factory '{factory_id}' tidak ditemukan.")
    twin = await service.get_full_twin(factory_id)
    return build_rl_inputs(twin, end_state=end_state, working_state=working_state)
