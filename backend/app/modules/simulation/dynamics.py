# backend/app/modules/simulation/dynamics.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

WorkerState = Literal["active", "idle", "on_break", "handover", "rework", "off_shift"]

PHYSICAL_WEIGHT: dict[str, float] = {"low": 0.70, "medium": 1.00, "high": 1.35}

ERROR_CONSEQUENCE: dict[str, dict[str, float]] = {
    "low": {"rework_cycles": 0.25, "scrap_ratio": 0.02, "downtime_ticks": 0.0},
    "moderate": {"rework_cycles": 0.50, "scrap_ratio": 0.05, "downtime_ticks": 0.0},
    "high": {"rework_cycles": 1.00, "scrap_ratio": 0.12, "downtime_ticks": 1.0},
    "critical": {"rework_cycles": 1.50, "scrap_ratio": 0.25, "downtime_ticks": 3.0},
}

BASE_SPEED_FLOOR = 0.55
BASE_SPEED_SPAN = 0.65
EXPERIENCE_CAP = 0.15
EXPERIENCE_DIVISOR = 40.0

FATIGUE_SPEED_PENALTY = 0.45
STRESS_SPEED_PENALTY = 0.20
HANDOVER_SPEED_FACTOR = 0.50

FATIGUE_PER_MINUTE = 0.0016
STRESS_PER_MINUTE = 0.0011
BREAK_RECOVERY_PER_MINUTE = 0.0045
IDLE_RECOVERY_RATIO = 0.40

COLLABORATION_CONGESTION = 0.12
BASE_ERROR_RATE = 0.004

SPEED_FLOOR = 0.15
SPEED_CEILING = 2.50


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass
class WorkerProfile:
    worker_id: str
    name: str = ""
    years_of_experience: float = 0.0
    baseline_physical_stamina: float = 0.5
    cognitive_resilience: float = 0.5
    skills: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "WorkerProfile":
        demographics = record.get("demographics") or {}
        return cls(
            worker_id=str(record.get("worker_id") or ""),
            name=str(record.get("name") or record.get("worker_id") or ""),
            years_of_experience=float(demographics.get("years_of_experience") or 0.0),
            baseline_physical_stamina=float(
                demographics.get("baseline_physical_stamina") or 0.5
            ),
            cognitive_resilience=float(demographics.get("cognitive_resilience") or 0.5),
            skills=[str(item) for item in (record.get("skills") or [])],
        )


@dataclass
class JobDemand:
    job_id: str
    required_cognitive_focus: float = 0.5
    physical_demand_level: str = "medium"
    task_complexity: float = 0.5
    error_severity: str = "moderate"
    required_skills: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, job_id: str, demands: dict[str, Any],
                    required_skills: list[str] | None = None) -> "JobDemand":
        return cls(
            job_id=job_id,
            required_cognitive_focus=float(demands.get("required_cognitive_focus") or 0.5),
            physical_demand_level=str(demands.get("physical_demand_level") or "medium"),
            task_complexity=float(demands.get("task_complexity") or 0.5),
            error_severity=str(demands.get("error_severity") or "moderate"),
            required_skills=list(required_skills or []),
        )


def skill_match_ratio(worker: WorkerProfile, demand: JobDemand) -> float:
    if not demand.required_skills:
        return 0.5

    owned = {token.casefold() for skill in worker.skills for token in skill.split()}
    matched = 0

    for required in demand.required_skills:
        tokens = {token.casefold() for token in required.split()}
        if tokens & owned:
            matched += 1

    return matched / len(demand.required_skills)


def resolve_compatibility(
    worker: WorkerProfile,
    demand: JobDemand,
    matrix_score: float | None = None,
) -> float:
    """Skor kompatibilitas 0..1 dari matriks GNN/LLM, dengan fallback heuristik."""
    if matrix_score is not None:
        return clamp(float(matrix_score), 0.0, 1.0)

    skill_component = skill_match_ratio(worker, demand)
    experience_component = clamp(worker.years_of_experience / 15.0, 0.0, 1.0)
    resilience_gap = clamp(
        1.0 - abs(demand.required_cognitive_focus - worker.cognitive_resilience), 0.0, 1.0
    )
    stamina_gap = clamp(
        1.0 - abs(PHYSICAL_WEIGHT.get(demand.physical_demand_level, 1.0) - 1.0)
        + (worker.baseline_physical_stamina - 0.5),
        0.0,
        1.0,
    )

    return clamp(
        0.40 * skill_component
        + 0.25 * experience_component
        + 0.20 * resilience_gap
        + 0.15 * stamina_gap,
        0.0,
        1.0,
    )


def worker_speed_factor(
    worker: WorkerProfile,
    demand: JobDemand,
    compatibility: float,
    fatigue: float,
    stress: float,
    state: WorkerState = "active",
) -> float:
    """Kecepatan relatif satu pekerja terhadap cycle time nominal stasiun."""
    if state in ("idle", "on_break", "off_shift"):
        return 0.0

    base = BASE_SPEED_FLOOR + BASE_SPEED_SPAN * compatibility
    experience_bonus = min(EXPERIENCE_CAP, worker.years_of_experience / EXPERIENCE_DIVISOR)

    fatigue_factor = 1.0 - FATIGUE_SPEED_PENALTY * clamp(fatigue, 0.0, 1.0)
    stress_factor = 1.0 - STRESS_SPEED_PENALTY * clamp(stress, 0.0, 1.0)

    speed = (base + experience_bonus) * fatigue_factor * stress_factor

    if state == "handover":
        speed *= HANDOVER_SPEED_FACTOR
    elif state == "rework":
        speed *= 0.65

    return clamp(speed, SPEED_FLOOR, SPEED_CEILING)


def station_speed_factor(worker_speeds: list[float]) -> float:
    """
    Agregasi multi-worker dengan diminishing return.
    Pekerja tercepat berkontribusi penuh; setiap tambahan operator pada stasiun
    yang sama dibobot 1 / (1 + congestion * rank) untuk memodelkan kongesti ruang
    kerja, serah-terima material, dan tumpang tindih tugas.
    """
    active = sorted((speed for speed in worker_speeds if speed > 0.0), reverse=True)

    if not active:
        return 0.0

    total = 0.0
    for rank, speed in enumerate(active):
        total += speed / (1.0 + COLLABORATION_CONGESTION * rank)

    return clamp(total, SPEED_FLOOR, SPEED_CEILING * len(active))


def advance_fatigue(
    fatigue: float,
    worker: WorkerProfile,
    demand: JobDemand,
    minutes: float,
    state: WorkerState,
    strain_index: float = 0.0,
) -> float:
    if state in ("on_break", "off_shift"):
        return clamp(fatigue - BREAK_RECOVERY_PER_MINUTE * minutes, 0.0, 1.0)

    if state == "idle":
        recovery = BREAK_RECOVERY_PER_MINUTE * IDLE_RECOVERY_RATIO * minutes
        return clamp(fatigue - recovery, 0.0, 1.0)

    physical_weight = PHYSICAL_WEIGHT.get(demand.physical_demand_level, 1.0)
    stamina_gap = clamp(1.60 - worker.baseline_physical_stamina, 0.5, 1.6)
    strain_multiplier = 1.0 + 0.5 * clamp(strain_index, 0.0, 1.0)

    delta = FATIGUE_PER_MINUTE * physical_weight * stamina_gap * strain_multiplier * minutes
    return clamp(fatigue + delta, 0.0, 1.0)


def advance_stress(
    stress: float,
    worker: WorkerProfile,
    demand: JobDemand,
    minutes: float,
    state: WorkerState,
    queue_pressure: float = 0.0,
) -> float:
    if state in ("on_break", "off_shift", "idle"):
        recovery = BREAK_RECOVERY_PER_MINUTE * IDLE_RECOVERY_RATIO * minutes
        return clamp(stress - recovery, 0.0, 1.0)

    resilience_gap = clamp(1.0 - worker.cognitive_resilience, 0.05, 1.0)
    pressure = 1.0 + clamp(queue_pressure, 0.0, 1.0)

    delta = (
        STRESS_PER_MINUTE
        * demand.required_cognitive_focus
        * resilience_gap
        * pressure
        * minutes
    )
    return clamp(stress + delta, 0.0, 1.0)


def error_probability(
    demand: JobDemand,
    compatibility: float,
    fatigue: float,
    stress: float,
) -> float:
    """Peluang human error per siklus produksi di stasiun ini."""
    return clamp(
        BASE_ERROR_RATE
        * (1.0 + 1.8 * clamp(fatigue, 0.0, 1.0))
        * (1.0 + 1.2 * clamp(stress, 0.0, 1.0))
        * (1.0 + demand.task_complexity)
        * (1.0 - 0.5 * clamp(compatibility, 0.0, 1.0)),
        0.0,
        0.45,
    )


def error_consequence(demand: JobDemand, batch_out: float) -> dict[str, float]:
    profile = ERROR_CONSEQUENCE.get(demand.error_severity, ERROR_CONSEQUENCE["moderate"])
    return {
        "rework_cycles": profile["rework_cycles"],
        "downtime_ticks": profile["downtime_ticks"],
        "defective_units": round(batch_out * profile["scrap_ratio"], 2),
        "good_units": round(batch_out * (1.0 - profile["scrap_ratio"]), 2),
    }


def burnout_risk(fatigue: float, stress: float) -> str:
    if fatigue > 0.65 or stress > 0.55:
        return "high"
    if fatigue > 0.40 or stress > 0.35:
        return "medium"
    return "low"


def resolve_worker_state(
    is_on_shift: bool,
    is_break: bool,
    is_handover_window: bool,
    has_material: bool,
    is_reworking: bool,
) -> WorkerState:
    """
    Prioritas state mengikuti realitas lantai produksi: keluar shift menang atas
    istirahat, istirahat menang atas serah-terima, dan bottleneck hulu (material
    kosong) menghasilkan Idle walaupun pekerja hadir dan siap bekerja.
    """
    if not is_on_shift:
        return "off_shift"
    if is_break:
        return "on_break"
    if is_handover_window:
        return "handover"
    if is_reworking:
        return "rework"
    if not has_material:
        return "idle"
    return "active"