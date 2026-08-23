# backend/app/modules/digital_twin_ingestion/schemas.py
"""
Skema data Pydantic modul Digital Twin Ingestion.
Sesuai dengan Standar Kontrak Data Digital Twin System.
Selaras dengan backend/app/agent/schemas/factory_md.schema.json
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseDTModel(BaseModel):
    """Base schema dengan alias camelCase otomatis dan dukungan ORM conversion."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# --- Tipe bersama ---

class Quantity(BaseDTModel):
    raw: str
    value: float | None = None
    unit: str | None = None
    unit_class: Literal["mass", "volume", "count", "power", "noise"] | None = None
    basis: str | None = None


AutomationLevel = Literal["manual", "semi_automated", "automated"]


# --- factory_info ---

class ProcessEdge(BaseDTModel):
    from_stage_id: str
    to_stage_id: str


class ParallelGroup(BaseDTModel):
    group_id: str
    depth: int
    steps: list[str] = Field(default_factory=list)
    lanes: list[str] = Field(default_factory=list)
    converges_to: str | None = None
    reasoning: str | None = None


class FactoryInfo(BaseDTModel):
    factory_id: str
    factory_name: str
    process_type: Literal["serial", "parallel", "hybrid"]
    declared_worker_count: int
    registered_worker_count: int
    layout_description: str
    workflow_sequence: list[str] = Field(default_factory=list)
    process_edges: list[ProcessEdge] = Field(default_factory=list)
    entry_stages: list[str] = Field(default_factory=list)
    terminal_stages: list[str] = Field(default_factory=list)
    parallel_groups: list[ParallelGroup] = Field(default_factory=list)
    lanes: list[str] = Field(default_factory=list)


VibrationHazardLevel = Literal["low", "medium", "high"]
PhysicalDemandLevel = Literal["low", "medium", "high"]
ErrorSeverity = Literal["low", "moderate", "high", "critical"]
BurnoutHazardRisk = Literal["low", "medium", "high", "critical"]


class RealtimeMetrics(BaseDTModel):
    current_fatigue_level: float
    current_stress_level: float
    burnout_hazard_risk: BurnoutHazardRisk


# --- assets ---

class AssetEnvironmentalFactors(BaseDTModel):
    power_consumption_watt: float | None = None
    noise_level_db: float | None = None
    vibration_hazard_level: VibrationHazardLevel
    physical_strain_index: float


class Asset(BaseDTModel):
    asset_id: str
    asset_name: str
    category: Literal[
        "machine",
        "measuring_equipment",
        "conveyor_automation",
        "environmental_chamber",
        "manual_station",
    ]
    units_available: int
    capacity_per_unit: Quantity
    total_capacity: Quantity
    automation_level: AutomationLevel
    is_automated: bool
    operational_cost_per_hour: float
    currency: str
    environmental_factors: AssetEnvironmentalFactors
    metric_derivation_reasoning: str | None = None


# --- process_stages ---

class ProcessStage(BaseDTModel):
    stage_id: str
    stage_name: str
    lane: str
    next_stage_id: str | None = None
    is_terminal: bool
    asset_id: str
    operator_task: str
    material_input: list[str] = Field(default_factory=list)
    material_output: list[str] = Field(default_factory=list)
    material_per_batch: list[Quantity] = Field(default_factory=list)
    flow_type: Literal["batch", "continuous"]
    cycle_time_seconds: float
    throughput: Quantity
    throughput_per_hour: float | None = None
    automation_level: AutomationLevel
    qc_requirement: str
    metric_derivation_reasoning: str | None = None


# --- shifts ---

class Shift(BaseDTModel):
    shift_id: str
    start_time: str
    end_time: str
    duration_hours: float
    crosses_midnight: bool


# --- job_descriptions ---

class Demands(BaseDTModel):
    required_cognitive_focus: float
    physical_demand_level: PhysicalDemandLevel
    task_complexity: float
    error_severity: ErrorSeverity


class JobDesk(BaseDTModel):
    job_id: str
    allocation_id: str
    job_title: str
    stage_id: str
    assigned_asset_id: str
    assigned_worker_ids: list[str] = Field(default_factory=list)
    shift_id: str
    headcount: int
    demands: Demands
    qc_requirement: str
    metric_derivation_reasoning: str | None = None


# --- workers (tidak berubah, tetap dari Agent B) ---

class Demographics(BaseDTModel):
    age: int
    gender: str
    years_of_experience: float
    baseline_physical_stamina: float
    cognitive_resilience: float


class ShiftContext(BaseDTModel):
    hours_worked_today: float
    consecutive_shifts: int


class Worker(BaseDTModel):
    worker_id: str
    name: str
    demographics: Demographics
    shift_context: ShiftContext
    skills: list[str] | None = None
    certifications: list[str] | None = None
    capabilities: list[str] | None = None


# --- floor_state (tidak berubah) ---

class StaffPosition(BaseDTModel):
    worker_id: str
    name: str
    current_station: str
    current_asset_id: str
    activity_status: str
    moving_to_next_step: str
    handoff_item: str


class FactoryFlowRightNow(BaseDTModel):
    snapshot_timestamp: str
    note: str | None = None
    staff_current_positions: list[StaffPosition] = Field(default_factory=list)


# --- compatibility (tidak berubah) ---

class Evaluations(BaseDTModel):
    overall_compatibility_score: float
    throughput_multiplier: float
    error_multiplier: float
    fatigue_accumulation_rate: float | None = None
    stress_sensitivity_factor: float | None = None


class CompatibilityEvaluation(BaseDTModel):
    worker_id: str
    job_id: str
    asset_id: str | None = None
    evaluations: Evaluations | dict[str, Any]
    llm_reasoning: str | None = ""


# --- gabungan ---

class DigitalTwin(BaseDTModel):
    simulation_id: str | None = None
    job_id: str | None = None
    factory_info: FactoryInfo
    assets: list[Asset] = Field(default_factory=list)
    process_stages: list[ProcessStage] = Field(default_factory=list)
    shifts: list[Shift] = Field(default_factory=list)
    job_desks: list[JobDesk] = Field(default_factory=list)
    workers: list[Worker] = Field(default_factory=list)
    factory_flow_rightnow: FactoryFlowRightNow | None = None
    llm_compatibility_and_evaluations: list[CompatibilityEvaluation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

# --- lifecycle factory & response gabungan ---

FactoryPipelineStatus = Literal[
    "initialized",
    "workers_ingested",
    "simulation_configured",
    "twin_ready",
]


class FactoryCreateRequest(BaseDTModel):
    factory_name: str = Field(..., min_length=1, max_length=255)
    factory_id: str | None = None
    process_type: Literal["serial", "parallel", "hybrid"] = "serial"
    declared_worker_count: int = Field(default=0, ge=0)
    layout_description: str = ""


class FactorySummary(BaseDTModel):
    factory_id: str
    factory_name: str
    process_type: str
    status: FactoryPipelineStatus
    declared_worker_count: int
    registered_worker_count: int
    assets_count: int
    process_stages_count: int
    shifts_count: int
    job_desks_count: int
    workers_count: int
    evaluations_count: int
    simulation_configured: bool
    created_at: str | None = None


class FactoryDigitalTwinResponse(BaseDTModel):
    factory_id: str
    status: FactoryPipelineStatus
    summary: FactorySummary
    digital_twin: DigitalTwin
    warnings: list[str] = Field(default_factory=list)