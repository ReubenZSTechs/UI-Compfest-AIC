# app/modules/rl_optimization/schemas.py
"""
Pydantic schemas untuk domain RL Optimization.

Mengikuti struktur factory_workflow_digital_twin.json:
- DigitalTwin        : factory_info, assets, job_desks, workers, compatibility matrix
- LiveSimulationState: factory_flow_rightnow + calculated_realtime_metrics
- OptimizationResult : hasil_optimisasi_skenario_optimal (Pareto-optimal scenarios)

Dipisah per grup dengan komentar section agar mudah dinavigasi mengingat
ukuran domain ini cukup besar.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# Enums — membatasi nilai string bebas jadi closed set (validasi otomatis)

class VibrationHazardLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PhysicalDemandLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ErrorSeverity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class BurnoutHazardRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ActivityStatus(str, Enum):
    processing = "processing"
    waiting_on_machine = "waiting_on_machine"
    idle_waiting_input = "idle_waiting_input"


class StaffAction(str, Enum):
    stay = "stay"
    moved = "moved"


class OptimizationJobStatusEnum(str, Enum):
    queued = "queued"
    running = "running"
    converged = "converged"
    failed = "failed"


# 1. DIGITAL TWIN — factory_info, assets, job_desks, workers

class FactoryInfo(BaseModel):
    factory_id: str
    factory_name: str
    workflow_sequence: list[str] = Field(
        ..., description="Urutan step workflow, mis. ['step_01_weighing', ...]"
    )


class EnvironmentalFactors(BaseModel):
    noise_level_db: float
    vibration_hazard_level: VibrationHazardLevel
    physical_strain_index: float = Field(..., ge=0.0, le=1.0)


class Asset(BaseModel):
    asset_id: str
    asset_name: str
    category: str
    workflow_step: str
    is_automated: bool
    base_throughput_capacity: float
    operational_cost_per_hour: float
    environmental_factors: EnvironmentalFactors
    metric_derivation_reasoning: str = Field(
        ..., description="Penjelasan kualitatif LLM di balik angka-angka di atas"
    )


class JobDemands(BaseModel):
    required_cognitive_focus: float = Field(..., ge=0.0, le=1.0)
    physical_demand_level: PhysicalDemandLevel
    task_complexity: float = Field(..., ge=0.0, le=1.0)
    error_severity: ErrorSeverity


class JobDesk(BaseModel):
    job_id: str
    job_title: str
    workflow_step: str
    assigned_asset_id: str
    demands: JobDemands
    qc_requirement: str
    metric_derivation_reasoning: str


class WorkerDemographics(BaseModel):
    age: int = Field(..., ge=15, le=70)
    gender: str
    years_of_experience: float = Field(..., ge=0)
    baseline_physical_stamina: float = Field(..., ge=0.0, le=1.0)
    cognitive_resilience: float = Field(..., ge=0.0, le=1.0)


class WorkerShiftContext(BaseModel):
    hours_worked_today: float = Field(..., ge=0.0, le=24.0)
    consecutive_shifts: int = Field(..., ge=0)


class Worker(BaseModel):
    worker_id: str
    name: str
    demographics: WorkerDemographics
    shift_context: WorkerShiftContext


class CompatibilityEvaluation(BaseModel):
    overall_compatibility_score: float = Field(..., ge=0.0, le=1.0)
    throughput_multiplier: float
    error_multiplier: float
    fatigue_accumulation_rate: float
    stress_sensitivity_factor: float


class CompatibilityEntry(BaseModel):
    """Satu baris matriks kompatibilitas N x M (worker x job x asset)."""

    worker_id: str
    job_id: str
    asset_id: str
    evaluations: CompatibilityEvaluation
    llm_reasoning: str


class DigitalTwin(BaseModel):
    """Struktur lengkap Single Source of Truth — setara factory_workflow_digital_twin.json."""

    model_config = ConfigDict(from_attributes=True)

    factory_info: FactoryInfo
    assets: list[Asset]
    job_desks: list[JobDesk]
    workers: list[Worker]
    llm_compatibility_and_evaluations: list[CompatibilityEntry]


class DigitalTwinResponse(DigitalTwin):
    """Response wrapper — bisa ditambah metadata tanpa mengubah bentuk inti."""

    updated_at: Optional[datetime] = None


class DigitalTwinUpsertRequest(BaseModel):
    """Payload saat LLM Text Parser mengirim ulang hasil parsing dokumen sumber."""

    factory_info: FactoryInfo
    assets: list[Asset]
    job_desks: list[JobDesk]
    workers: list[Worker]
    llm_compatibility_and_evaluations: list[CompatibilityEntry] = Field(
        default_factory=list,
        description="Boleh kosong jika compatibility matrix akan digenerate ulang oleh service.",
    )


# 2. LIVE SIMULATION STATE — factory_flow_rightnow + calculated_realtime_metrics

class StaffCurrentPosition(BaseModel):
    worker_id: str
    name: str
    current_station: str
    current_asset_id: str
    activity_status: ActivityStatus
    moving_to_next_step: str
    handoff_item: str


class FactoryFlowRightNow(BaseModel):
    snapshot_timestamp: datetime
    note: str
    staff_current_positions: list[StaffCurrentPosition]


class RealtimeMetrics(BaseModel):
    current_fatigue_level: float = Field(..., ge=0.0, le=1.0)
    current_stress_level: float = Field(..., ge=0.0, le=1.0)
    effective_throughput_per_hour: float
    effective_error_probability: float = Field(..., ge=0.0, le=1.0)
    burnout_hazard_risk: BurnoutHazardRisk


class CurrentAssignment(BaseModel):
    worker_id: str
    assigned_job_id: str
    assigned_asset_id: str
    calculated_realtime_metrics: RealtimeMetrics


class LiveSimulationState(BaseModel):
    current_assignments: list[CurrentAssignment]
    system_bottlenecks: list[str]
    analytical_insight_summary: str


class LiveSimulationResponse(BaseModel):
    factory_id: str
    factory_flow_rightnow: FactoryFlowRightNow
    live_simulation_state: LiveSimulationState


class BottleneckInsight(BaseModel):
    """Endpoint shortcut — dipakai untuk dashboard alert."""

    workflow_step: str
    worker_id: str
    burnout_hazard_risk: BurnoutHazardRisk
    current_fatigue_level: float
    current_stress_level: float
    insight: str


# 3. OPTIMIZATION — request, job status, scenario hasil training

class OptimizationConstraints(BaseModel):
    hiring_allowed: bool = False
    fire_or_mutation_allowed: bool = False
    automation_allowed: bool = False
    capex_rp: float = Field(0, ge=0)


class OptimizationRequest(BaseModel):
    factory_id: str
    constraints: OptimizationConstraints = Field(default_factory=OptimizationConstraints)


class OptimizationJobAccepted(BaseModel):
    job_id: UUID
    status: OptimizationJobStatusEnum = OptimizationJobStatusEnum.queued
    factory_id: str
    submitted_at: datetime


class OptimizationJobStatus(BaseModel):
    job_id: UUID
    factory_id: str
    status: OptimizationJobStatusEnum
    algorithm: str = "Maskable PPO (sb3-contrib)"
    total_episodes: Optional[int] = None
    progress_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class BaselineMetrics(BaseModel):
    throughput_per_hour: float
    human_error_rate_pct: float
    total_op_cost_per_hour_rp: float


class MetricComparisonDirection(str, Enum):
    up = "up"      # perubahan ini menguntungkan
    down = "down"  # perubahan ini merugikan (mis. cost naik)


class MetricComparison(BaseModel):
    before: float
    after: float
    delta_pct: float
    direction: MetricComparisonDirection


class ScenarioMetrics(BaseModel):
    throughput_per_hour: MetricComparison
    human_error_rate_pct: MetricComparison
    total_op_cost_per_hour_rp: MetricComparison


class ReallocationMove(BaseModel):
    move_id: str
    worker_id: str
    name: str
    from_station: str
    to_station: str
    reason: str


class AssetUpgrade(BaseModel):
    asset_id: str
    old_asset_name: str
    new_asset_name: str
    workflow_step: str
    is_automated: bool
    capex_rp: float
    reason: Optional[str] = None


class NewHire(BaseModel):
    worker_id: str
    name: str
    assigned_station: str
    purpose: str
    capex_rp: float


class OptimalStaffPosition(BaseModel):
    worker_id: str
    name: str
    current_station_rightnow: str
    optimal_station: str
    action: StaffAction
    move_id: Optional[str] = None


class FactoryFlowOptimal(BaseModel):
    note: str
    reallocation_moves: list[ReallocationMove] = Field(default_factory=list)
    asset_upgrades: list[AssetUpgrade] = Field(default_factory=list)
    new_hires: list[NewHire] = Field(default_factory=list)
    new_cross_compatibility_evaluations: list[CompatibilityEntry] = Field(
        default_factory=list
    )
    optimal_staff_positions: list[OptimalStaffPosition] = Field(default_factory=list)
    residual_bottleneck: Optional[str] = None
    rl_reasoning: str


class ScenarioConstraints(OptimizationConstraints):
    """Alias semantik — constraint yang benar-benar dipakai skenario ini."""
    pass


class OptimizationScenario(BaseModel):
    scenario_id: str
    title: str
    recommended: bool
    description: str
    constraints: ScenarioConstraints
    metrics: ScenarioMetrics
    insight: str
    assumption_flag: Optional[str] = Field(
        None,
        description="Diisi jika angka metrik belum diverifikasi dari training RL aktual",
    )
    factory_flow_optimal: FactoryFlowOptimal


class OptimizationResultMeta(BaseModel):
    status: str = "RL CONVERGED"
    total_episodes: int
    algorithm: str = "Maskable PPO (sb3-contrib)"
    baseline: BaselineMetrics
    description: str


class OptimizationResult(BaseModel):
    """Setara hasil_optimisasi_skenario_optimal — dipakai internal setelah job selesai."""

    job_id: UUID
    meta: OptimizationResultMeta
    scenarios: list[OptimizationScenario]


# 4. Response wrappers untuk endpoint spesifik

class ApplyScenarioResponse(BaseModel):
    job_id: UUID
    scenario_id: str
    applied_at: datetime
    updated_factory_flow_rightnow: FactoryFlowRightNow
    message: str = "Skenario berhasil diterapkan ke live simulation state."
