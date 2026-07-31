from typing import List
from pydantic import BaseModel


class FactoryInfo(BaseModel):
    factory_id: str
    factory_name: str
    workflow_sequence: List[str]


class EnvironmentalFactors(BaseModel):
    noise_level_db: float
    vibration_hazard_level: str  # "low" | "medium" | "high"
    physical_strain_index: float


class Asset(BaseModel):
    asset_id: str
    asset_name: str
    category: str
    workflow_step: str
    is_automated: bool
    base_throughput_capacity: float
    operational_cost_per_hour: float
    environmental_factors: EnvironmentalFactors
    metric_derivation_reasoning: str


class Demands(BaseModel):
    required_cognitive_focus: float
    physical_demand_level: str  # "low" | "medium" | "high"
    task_complexity: float
    error_severity: str  # "low" | "moderate" | "high" | "critical"


class JobDesk(BaseModel):
    job_id: str
    job_title: str
    workflow_step: str
    assigned_asset_id: str
    demands: Demands
    qc_requirement: str
    metric_derivation_reasoning: str


class Demographics(BaseModel):
    age: int
    gender: str
    years_of_experience: int
    baseline_physical_stamina: float
    cognitive_resilience: float


class ShiftContext(BaseModel):
    hours_worked_today: float
    consecutive_shifts: int


class Worker(BaseModel):
    worker_id: str
    name: str
    demographics: Demographics
    shift_context: ShiftContext


class StaffPosition(BaseModel):
    worker_id: str
    name: str
    current_station: str
    current_asset_id: str
    activity_status: str
    moving_to_next_step: str
    handoff_item: str


class FactoryFlowRightNow(BaseModel):
    snapshot_timestamp: str
    note: str
    staff_current_positions: List[StaffPosition]


class Evaluations(BaseModel):
    overall_compatibility_score: float
    throughput_multiplier: float
    error_multiplier: float
    fatigue_accumulation_rate: float
    stress_sensitivity_factor: float


class CompatibilityEvaluation(BaseModel):
    worker_id: str
    job_id: str
    asset_id: str
    evaluations: Evaluations
    llm_reasoning: str


class DigitalTwin(BaseModel):
    factory_info: FactoryInfo
    assets: List[Asset]
    job_desks: List[JobDesk]
    workers: List[Worker]
    factory_flow_rightnow: FactoryFlowRightNow
    llm_compatibility_and_evaluations: List[CompatibilityEvaluation]