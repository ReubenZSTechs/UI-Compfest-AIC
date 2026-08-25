# backend/app/modules/simulation/schemas.py
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from . import constants as C

BurnoutRisk = Literal["low", "medium", "high"]
AutomationLevel = Literal["manual", "semi_automated", "automated"]
UnitClass = Literal["mass", "volume", "count", "power", "noise"]
HazardLevel = Literal["low", "medium", "high"]
AssetCategory = Literal[
    "machine",
    "measuring_equipment",
    "conveyor_automation",
    "environmental_chamber",
    "manual_station",
]

_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ==========================================================================
# Kontrak GET /simulation/config (dipakai tick loop frontend, snake_case)
# ==========================================================================


class MaterialTemplate(BaseModel):
    name: str
    unit: str


class RealtimeMetrics(BaseModel):
    current_fatigue_level: float
    current_stress_level: float
    effective_throughput_per_hour: float
    effective_error_probability: float
    burnout_hazard_risk: BurnoutRisk
    throughput_multiplier: float


class SeedAssignment(BaseModel):
    worker_id: str
    assigned_job_id: str
    assigned_asset_id: str
    calculated_realtime_metrics: RealtimeMetrics

class WarehouseSource(BaseModel):
    warehouse_id: str
    warehouse_name: str
    material_name: str
    material_unit: str
    capacity: float
    feed_rate: float
    initial_stock: float
    replenish_per_tick: float
    supply_mode: str
    target_ordinals: list[int]


class OutputSink(BaseModel):
    output_id: str
    output_name: str
    material_name: str
    material_unit: str
    target_output_units: float
    accepts_defective: bool
    source_ordinals: list[int]


class ShiftBreakWindow(BaseModel):
    break_id: str
    start_elapsed_minutes: int
    end_elapsed_minutes: int
    label: str


class ShiftPlan(BaseModel):
    shift_id: str
    start_time: str
    end_time: str
    start_elapsed_minutes: int
    end_elapsed_minutes: int
    handover_minutes: int
    breaks: list[ShiftBreakWindow]


class ShiftRosterEntry(BaseModel):
    shift_id: str
    ordinal: int
    job_id: str
    worker_ids: list[str]


class WorkerRuntimeProfile(BaseModel):
    worker_id: str
    name: str
    years_of_experience: float
    baseline_physical_stamina: float
    cognitive_resilience: float
    skills: list[str]
    compatibility_by_job_id: dict[str, float]


class JobDemandProfile(BaseModel):
    job_id: str
    ordinal: int
    required_cognitive_focus: float
    physical_demand_level: str
    task_complexity: float
    error_severity: str
    required_skills: list[str]
    physical_strain_index: float

class SimulationConfig(BaseModel):
    """
    Satu-satunya sumber kebenaran untuk parameter simulasi. Frontend fetch ini
    sekali di awal, lalu menjalankan tick loop-nya sendiri memakai angka di sini.
    Key dict adalah ordinal step (1..N).
    """

    materials_by_ordinal: dict[int, MaterialTemplate]
    step_names: dict[int, str]
    step_cost_base: dict[int, int]
    capacity_by_ordinal: dict[int, float]
    batch_in_by_ordinal: dict[int, float]
    batch_out_by_ordinal: dict[int, float]
    cycle_ticks_by_ordinal: dict[int, int]
    step_ids_by_ordinal: dict[int, str] = Field(default_factory=dict)
    station_edges: dict[int, list[int]] = Field(default_factory=dict)
    entry_ordinals: list[int] = Field(default_factory=list)
    terminal_ordinals: list[int] = Field(default_factory=list)
    ordinal_by_job_id: dict[str, int] = Field(default_factory=dict)

    bottleneck_fill_threshold: float
    idle_qty_threshold: float
    station_1_safety_margin: float

    warehouse_capacity: float
    warehouse_feed_rate: float
    warehouse_step_id: str

    worker_throughput_multiplier: dict[str, float]
    seed_assignments: list[SeedAssignment]

    shift_start_minutes: int
    break_start_elapsed: int
    break_end_elapsed: int
    shift_end_elapsed: int

    analytical_insight_summary: str
    target_output_units: float
    initial_batch_seq: int

    warehouses: list[WarehouseSource] = Field(default_factory=list)
    outputs: list[OutputSink] = Field(default_factory=list)
    shift_plans: list[ShiftPlan] = Field(default_factory=list)
    shift_roster: list[ShiftRosterEntry] = Field(default_factory=list)
    worker_profiles: list[WorkerRuntimeProfile] = Field(default_factory=list)
    job_demands: list[JobDemandProfile] = Field(default_factory=list)


# ==========================================================================
# Kontrak perancangan flowchart manual (camelCase alias untuk frontend)
# ==========================================================================


class BaseSimModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class QuantityInput(BaseSimModel):
    raw: str | None = None
    value: float | None = None
    unit: str | None = None
    unit_class: UnitClass | None = None
    basis: str | None = None

    def normalized(self) -> dict[str, Any]:
        text = self.raw
        if not text:
            text = f"{self.value} {self.unit}" if self.value is not None and self.unit else "n/a"
        return {
            "raw": text,
            "value": self.value,
            "unit": self.unit,
            "unit_class": self.unit_class,
            "basis": self.basis,
        }


class EnvironmentalFactorsInput(BaseSimModel):
    power_consumption_watt: float | None = None
    noise_level_db: float | None = None
    vibration_hazard_level: HazardLevel = "low"
    physical_strain_index: float = Field(default=0.0, ge=0, le=1)


class AssetInput(BaseSimModel):
    asset_id: str
    asset_name: str
    category: AssetCategory = "manual_station"
    units_available: int = Field(default=1, ge=0)
    capacity_per_unit: QuantityInput = Field(default_factory=QuantityInput)
    total_capacity: QuantityInput = Field(default_factory=QuantityInput)
    automation_level: AutomationLevel = "manual"
    is_automated: bool = False
    operational_cost_per_hour: float = Field(default=0.0, ge=0)
    currency: str = "IDR"
    environmental_factors: EnvironmentalFactorsInput = Field(
        default_factory=EnvironmentalFactorsInput
    )
    metric_derivation_reasoning: str | None = None


class ProcessStageInput(BaseSimModel):
    stage_id: str
    stage_name: str
    lane: str = "main"
    next_stage_id: str | None = None
    is_terminal: bool = False
    asset_id: str
    operator_task: str = ""
    material_input: list[str] = Field(default_factory=list)
    material_output: list[str] = Field(default_factory=list)
    material_per_batch: list[QuantityInput] = Field(default_factory=list)
    flow_type: Literal["batch", "continuous"] = "batch"
    cycle_time_seconds: float = Field(default=60.0, gt=0)
    throughput: QuantityInput = Field(default_factory=QuantityInput)
    throughput_per_hour: float | None = None
    automation_level: AutomationLevel = "manual"
    qc_requirement: str = ""
    metric_derivation_reasoning: str | None = None


class ShiftInput(BaseSimModel):
    shift_id: str
    start_time: str
    end_time: str
    duration_hours: float | None = None
    crosses_midnight: bool | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        if not _TIME_PATTERN.match(value):
            raise ValueError(f"Format jam tidak valid: '{value}' (harus HH:MM, mis. 08:00)")
        return value

    def normalized(self) -> dict[str, Any]:
        start_h, start_m = (int(x) for x in self.start_time.split(":"))
        end_h, end_m = (int(x) for x in self.end_time.split(":"))
        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m

        crosses = self.crosses_midnight
        if crosses is None:
            crosses = end_total <= start_total

        if self.duration_hours is not None:
            duration = self.duration_hours
        else:
            delta = end_total - start_total if not crosses else end_total + 24 * 60 - start_total
            duration = round(delta / 60, 2)

        return {
            "shift_id": self.shift_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_hours": duration,
            "crosses_midnight": crosses,
        }


class DemandsInput(BaseSimModel):
    required_cognitive_focus: float = Field(default=0.5, ge=0, le=1)
    physical_demand_level: HazardLevel = "medium"
    task_complexity: float = Field(default=0.5, ge=0, le=1)
    error_severity: Literal["low", "moderate", "high", "critical"] = "moderate"


class JobDeskInput(BaseSimModel):
    job_id: str
    allocation_id: str | None = None
    job_title: str
    stage_id: str
    assigned_asset_id: str
    assigned_worker_ids: list[str] = Field(default_factory=list)
    shift_id: str
    headcount: int = Field(default=1, ge=1)
    demands: DemandsInput = Field(default_factory=DemandsInput)
    qc_requirement: str = ""
    metric_derivation_reasoning: str | None = None


class FactoryGraphInput(BaseSimModel):
    process_type: Literal["serial", "parallel", "hybrid"] = "serial"
    layout_description: str | None = None
    workflow_sequence: list[str] = Field(default_factory=list)
    process_edges: list[dict[str, Any]] = Field(default_factory=list)
    entry_stages: list[str] = Field(default_factory=list)
    terminal_stages: list[str] = Field(default_factory=list)
    parallel_groups: list[dict[str, Any]] | None = None
    lanes: list[str] = Field(default_factory=list)


class StationInput(BaseSimModel):
    ordinal: int = Field(ge=1)
    stage_id: str | None = None
    step_name: str
    material_name: str = "Material"
    material_unit: str = "pcs"
    step_cost_base: int = Field(default=0, ge=0)
    capacity: float = Field(gt=0)
    batch_in: float = Field(gt=0)
    batch_out: float = Field(gt=0)
    cycle_ticks: int = Field(default=1, ge=1)

class WarehouseSourceInput(BaseSimModel):
    warehouse_id: str
    warehouse_name: str = "Gudang"
    material_name: str = "Bahan Baku"
    material_unit: str = "pcs"
    capacity: float = Field(default=C.WAREHOUSE_CAPACITY, gt=0)
    feed_rate: float = Field(default=C.WAREHOUSE_FEED_RATE, gt=0)
    initial_stock: float | None = None
    replenish_per_tick: float = Field(default=0.0, ge=0)
    supply_mode: Literal["finite", "continuous"] = "finite"
    target_stage_ids: list[str] = Field(default_factory=list)


class OutputSinkInput(BaseSimModel):
    output_id: str
    output_name: str = "Finished Goods"
    material_name: str = "Produk Jadi"
    material_unit: str = "pcs"
    target_output_units: float = Field(default=C.TARGET_OUTPUT_UNITS, gt=0)
    accepts_defective: bool = False
    source_stage_ids: list[str] = Field(default_factory=list)


class ShiftBreakInput(BaseSimModel):
    break_id: str = "break-01"
    start_elapsed_minutes: int = Field(ge=0)
    duration_minutes: int = Field(default=60, ge=0)
    label: str = "Istirahat"


class ShiftPlanInput(BaseSimModel):
    shift_id: str
    start_time: str
    end_time: str
    duration_hours: float | None = None
    crosses_midnight: bool | None = None
    handover_minutes: int = Field(default=15, ge=0, le=120)
    breaks: list[ShiftBreakInput] = Field(default_factory=list)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, value: str) -> str:
        if not _TIME_PATTERN.match(value):
            raise ValueError(f"Format jam tidak valid: '{value}' (harus HH:MM, mis. 08:00)")
        return value


class ShiftWorkerAssignmentInput(BaseSimModel):
    shift_id: str
    stage_id: str
    job_id: str | None = None
    worker_ids: list[str] = Field(default_factory=list)


class WorkerRuntimeProfileInput(BaseSimModel):
    worker_id: str
    name: str = ""
    years_of_experience: float = Field(default=0.0, ge=0)
    baseline_physical_stamina: float = Field(default=0.5, ge=0, le=1)
    cognitive_resilience: float = Field(default=0.5, ge=0, le=1)
    skills: list[str] = Field(default_factory=list)
    compatibility_by_job_id: dict[str, float] = Field(default_factory=dict)

class SimulationSettingsInput(BaseSimModel):
    bottleneck_fill_threshold: float = Field(default=C.BOTTLENECK_FILL_THRESHOLD, ge=0, le=1)
    idle_qty_threshold: float = Field(default=C.IDLE_QTY_THRESHOLD, ge=0, le=1)
    station_1_safety_margin: float = Field(default=C.STATION_1_SAFETY_MARGIN, ge=0, le=1)

    warehouse_capacity: float = Field(default=C.WAREHOUSE_CAPACITY, gt=0)
    warehouse_feed_rate: float = Field(default=C.WAREHOUSE_FEED_RATE, gt=0)
    warehouse_step_id: str = C.WAREHOUSE_STEP_ID

    shift_start_minutes: int = Field(default=C.SHIFT_START_MINUTES, ge=0)
    break_start_elapsed: int = Field(default=C.BREAK_START_ELAPSED, ge=0)
    break_end_elapsed: int = Field(default=C.BREAK_END_ELAPSED, ge=0)
    shift_end_elapsed: int = Field(default=C.SHIFT_END_ELAPSED, ge=0)

    analytical_insight_summary: str = C.INSIGHT
    target_output_units: float = Field(default=C.TARGET_OUTPUT_UNITS, gt=0)
    initial_batch_seq: int = Field(default=1, ge=0)


class WorkerMultiplierInput(BaseSimModel):
    worker_id: str
    multiplier: float = Field(default=1.0, gt=0)


class SeedAssignmentInput(BaseSimModel):
    worker_id: str
    assigned_job_id: str
    assigned_asset_id: str
    realtime_metrics: dict[str, Any] | None = None


class SimulationDesignRequest(BaseSimModel):
    """
    Payload flowchart manual dari UI. Dipetakan ke tabel pada
    `digital_twin_ingestion/models.py` (Asset, ProcessStage, Shift, JobDesk)
    dan `simulation/models.py` (SimulationStation, SimulationSettings,
    WorkerThroughputMultiplier, SimulationSeedAssignment).
    """

    factory_info: FactoryGraphInput = Field(default_factory=FactoryGraphInput)
    assets: list[AssetInput] = Field(default_factory=list)
    process_stages: list[ProcessStageInput] = Field(default_factory=list)
    shifts: list[ShiftInput] = Field(default_factory=list)
    job_desks: list[JobDeskInput] = Field(default_factory=list)
    stations: list[StationInput] = Field(default_factory=list)
    settings: SimulationSettingsInput | None = None
    worker_multipliers: list[WorkerMultiplierInput] = Field(default_factory=list)
    seed_assignments: list[SeedAssignmentInput] = Field(default_factory=list)
    prune_missing: bool = True
    warehouses: list[WarehouseSourceInput] = Field(default_factory=list)
    outputs: list[OutputSinkInput] = Field(default_factory=list)
    shift_plans: list[ShiftPlanInput] = Field(default_factory=list)
    shift_assignments: list[ShiftWorkerAssignmentInput] = Field(default_factory=list)
    worker_profiles: list[WorkerRuntimeProfileInput] = Field(default_factory=list)


class SimulationDesignResponse(BaseSimModel):
    factory_id: str
    assets_saved: int = 0
    process_stages_saved: int = 0
    shifts_saved: int = 0
    job_desks_saved: int = 0
    stations_saved: int = 0
    worker_multipliers_saved: int = 0
    seed_assignments_saved: int = 0
    warnings: list[str] = Field(default_factory=list)


class FlowchartNode(BaseSimModel):
    stage_id: str
    stage_name: str
    lane: str
    ordinal: int | None = None
    asset_id: str
    next_stage_id: str | None = None
    is_terminal: bool = False
    job_ids: list[str] = Field(default_factory=list)
    worker_ids: list[str] = Field(default_factory=list)


class FlowchartEdge(BaseSimModel):
    from_stage_id: str
    to_stage_id: str


class SimulationOverview(BaseSimModel):
    factory_id: str
    factory_name: str
    is_configured: bool
    process_type: str
    workflow_sequence: list[str] = Field(default_factory=list)
    entry_stages: list[str] = Field(default_factory=list)
    terminal_stages: list[str] = Field(default_factory=list)
    lanes: list[str] = Field(default_factory=list)
    nodes: list[FlowchartNode] = Field(default_factory=list)
    edges: list[FlowchartEdge] = Field(default_factory=list)
    config: SimulationConfig
    updated_at: str | None = None
    warnings: list[str] = Field(default_factory=list)