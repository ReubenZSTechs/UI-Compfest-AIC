# backend/app/modules/digital_twin_ingestion/schemas.py
"""
Skema data Pydantic modul Digital Twin Ingestion.
Sesuai dengan Standar Kontrak Data Digital Twin System.
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


class ParallelGroup(BaseDTModel):
    group_id: str
    steps: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class FactoryInfo(BaseDTModel):
    factory_id: str
    factory_name: str
    workflow_sequence: list[str] = Field(default_factory=list)
    process_type: str | None = None
    declared_worker_count: int | None = None
    layout_description: str | None = None
    parallel_groups: list[ParallelGroup] | None = None


VibrationHazardLevel = Literal["low", "medium", "high"]
PhysicalDemandLevel = Literal["low", "medium", "high"]
ErrorSeverity = Literal["low", "moderate", "high", "critical"]
BurnoutHazardRisk = Literal["low", "medium", "high", "critical"]


class RealtimeMetrics(BaseDTModel):
    current_fatigue_level: float
    current_stress_level: float
    burnout_hazard_risk: BurnoutHazardRisk


class EnvironmentalFactors(BaseDTModel):
    noise_level_db: float
    vibration_hazard_level: VibrationHazardLevel
    physical_strain_index: float


class Asset(BaseDTModel):
    asset_id: str
    asset_name: str
    category: str
    workflow_step: str
    is_automated: bool
    base_throughput_capacity: float
    operational_cost_per_hour: float
    environmental_factors: EnvironmentalFactors
    metric_derivation_reasoning: str | None = None
    units_available: int | None = None


class Demands(BaseDTModel):
    required_cognitive_focus: float
    physical_demand_level: PhysicalDemandLevel
    task_complexity: float
    error_severity: ErrorSeverity


class JobDesk(BaseDTModel):
    job_id: str
    job_title: str
    workflow_step: str
    assigned_asset_id: str
    demands: Demands
    qc_requirement: str
    metric_derivation_reasoning: str | None = None


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


class DigitalTwin(BaseDTModel):
    simulation_id: str | None = None
    job_id: str | None = None
    factory_info: FactoryInfo
    assets: list[Asset] = Field(default_factory=list)
    job_desks: list[JobDesk] = Field(default_factory=list)
    workers: list[Worker] = Field(default_factory=list)
    factory_flow_rightnow: FactoryFlowRightNow | None = None
    llm_compatibility_and_evaluations: list[CompatibilityEvaluation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)