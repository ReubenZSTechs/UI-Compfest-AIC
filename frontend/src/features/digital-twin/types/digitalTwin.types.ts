// ============================================
// Factory Info
// ============================================
export interface FactoryInfo {
  factory_id: string;
  factory_name: string;
  workflow_sequence: string[];
}

// ============================================
// Assets
// ============================================
export type AssetCategory =
  | "measuring_equipment"
  | "machine"
  | "conveyor_automation"
  | "environmental_chamber"
  | "manual_station";

export type VibrationHazardLevel = "low" | "medium" | "high";

export interface EnvironmentalFactors {
  noise_level_db: number;
  vibration_hazard_level: VibrationHazardLevel;
  physical_strain_index: number; // 0.0 - 1.0
}

export interface Asset {
  asset_id: string;
  asset_name: string;
  category: AssetCategory;
  workflow_step: string;
  is_automated: boolean;
  base_throughput_capacity: number;
  operational_cost_per_hour: number;
  environmental_factors: EnvironmentalFactors;
  metric_derivation_reasoning: string;
}

// ============================================
// Job Desks
// ============================================
export type PhysicalDemandLevel = "low" | "medium" | "high";
export type ErrorSeverity = "low" | "moderate" | "high" | "critical";

export interface JobDemands {
  required_cognitive_focus: number; // 0.0 - 1.0
  physical_demand_level: PhysicalDemandLevel;
  task_complexity: number; // 0.0 - 1.0
  error_severity: ErrorSeverity;
}

export interface JobDesk {
  job_id: string;
  job_title: string;
  workflow_step: string;
  assigned_asset_id: string;
  demands: JobDemands;
  qc_requirement: string;
  metric_derivation_reasoning: string;
}

// ============================================
// Workers
// ============================================
export interface WorkerDemographics {
  age: number;
  gender: "male" | "female";
  years_of_experience: number;
  baseline_physical_stamina: number; // 0.0 - 1.0
  cognitive_resilience: number; // 0.0 - 1.0
}

export interface ShiftContext {
  hours_worked_today: number;
  consecutive_shifts: number;
}

export interface Worker {
  worker_id: string;
  name: string;
  demographics: WorkerDemographics;
  shift_context: ShiftContext;
}

// ============================================
// Live Factory Flow (snapshot posisi staf real-time)
// ============================================
export type ActivityStatus = "processing" | "waiting_on_machine" | "idle_waiting_input";

export interface StaffPosition {
  worker_id: string;
  name: string;
  current_station: string;
  current_asset_id: string;
  activity_status: ActivityStatus;
  moving_to_next_step: string;
  handoff_item: string;
}

export interface FactoryFlowRightNow {
  snapshot_timestamp: string; // ISO 8601
  note: string;
  staff_current_positions: StaffPosition[];
}

// ============================================
// Compatibility Matrix & LLM Evaluations
// ============================================
export type BurnoutHazardRisk = "low" | "medium" | "high" | "critical";

export interface CompatibilityEvaluationMetrics {
  overall_compatibility_score: number; // 0.0 - 1.0
  throughput_multiplier: number;
  error_multiplier: number;
  fatigue_accumulation_rate: number;
  stress_sensitivity_factor: number;
}

export interface CompatibilityEvaluation {
  worker_id: string;
  job_id: string;
  asset_id: string;
  evaluations: CompatibilityEvaluationMetrics;
  llm_reasoning: string;
}

// ============================================
// Root: Digital Twin (Single Source of Truth)
// ============================================
export interface DigitalTwin {
  factory_info: FactoryInfo;
  assets: Asset[];
  job_desks: JobDesk[];
  workers: Worker[];
  factory_flow_rightnow: FactoryFlowRightNow;
  llm_compatibility_and_evaluations: CompatibilityEvaluation[];
}

// ============================================
// Live Simulation State (real-time metrics per worker)
// ============================================
export interface RealtimeMetrics {
  current_fatigue_level: number;
  current_stress_level: number;
  effective_throughput_per_hour: number;
  effective_error_probability: number;
  burnout_hazard_risk: BurnoutHazardRisk;
}

export interface CurrentAssignment {
  worker_id: string;
  assigned_job_id: string;
  assigned_asset_id: string;
  calculated_realtime_metrics: RealtimeMetrics;
}

export interface LiveSimulationState {
  current_assignments: CurrentAssignment[];
  system_bottlenecks: string[];
  analytical_insight_summary: string;
}