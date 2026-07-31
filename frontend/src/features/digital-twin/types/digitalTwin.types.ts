export interface FactoryInfo {
  factory_id: string;
  factory_name: string;
  workflow_sequence: string[];
}

export type VibrationHazardLevel = "low" | "medium" | "high";
export type PhysicalDemandLevel = "low" | "medium" | "high";
export type ErrorSeverity = "low" | "moderate" | "high" | "critical";

export type BurnoutHazardRisk = "low" | "medium" | "high" | "critical";

export interface RealtimeMetrics {
  current_fatigue_level: number;
  current_stress_level: number;
  burnout_hazard_risk: BurnoutHazardRisk;
}

export interface EnvironmentalFactors {
  noise_level_db: number;
  vibration_hazard_level: VibrationHazardLevel;
  physical_strain_index: number;
}

export interface Asset {
  asset_id: string;
  asset_name: string;
  category: string;
  workflow_step: string;
  is_automated: boolean;
  base_throughput_capacity: number;
  operational_cost_per_hour: number;
  environmental_factors: EnvironmentalFactors;
  metric_derivation_reasoning: string;
}

export type AssetCategory = Asset["category"];

export interface Demands {
  required_cognitive_focus: number;
  physical_demand_level: PhysicalDemandLevel;
  task_complexity: number;
  error_severity: ErrorSeverity;
}

export interface JobDesk {
  job_id: string;
  job_title: string;
  workflow_step: string;
  assigned_asset_id: string;
  demands: Demands;
  qc_requirement: string;
  metric_derivation_reasoning: string;
}

export interface Demographics {
  age: number;
  gender: string;
  years_of_experience: number;
  baseline_physical_stamina: number;
  cognitive_resilience: number;
}

export interface ShiftContext {
  hours_worked_today: number;
  consecutive_shifts: number;
}

export interface Worker {
  worker_id: string;
  name: string;
  demographics: Demographics;
  shift_context: ShiftContext;
}

export interface StaffPosition {
  worker_id: string;
  name: string;
  current_station: string;
  current_asset_id: string;
  activity_status: string;
  moving_to_next_step: string;
  handoff_item: string;
}

export interface FactoryFlowRightNow {
  snapshot_timestamp: string;
  note: string;
  staff_current_positions: StaffPosition[];
}

export interface Evaluations {
  overall_compatibility_score: number;
  throughput_multiplier: number;
  error_multiplier: number;
  fatigue_accumulation_rate: number;
  stress_sensitivity_factor: number;
}

export interface CompatibilityEvaluation {
  worker_id: string;
  job_id: string;
  asset_id: string;
  evaluations: Evaluations;
  llm_reasoning: string;
}

export interface DigitalTwin {
  factory_info: FactoryInfo;
  assets: Asset[];
  job_desks: JobDesk[];
  workers: Worker[];
  factory_flow_rightnow: FactoryFlowRightNow;
  llm_compatibility_and_evaluations: CompatibilityEvaluation[];
}