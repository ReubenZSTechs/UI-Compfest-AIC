// features/simulation/types/simulation.types.ts

export type BurnoutRisk = 'low' | 'medium' | 'high';
export type StepStatus = 'normal' | 'bottleneck' | 'idle';
export type SimulationRunStatus = 'idle' | 'running' | 'paused' | 'completed';
export type OperationalStatus = 'working' | 'break' | 'shift_ended';

export type WorkerActivityState =
  | 'active'
  | 'idle'
  | 'on_break'
  | 'handover'
  | 'rework'
  | 'off_shift';

export interface ShiftBreakWindow {
  break_id: string;
  start_elapsed_minutes: number;
  end_elapsed_minutes: number;
  label: string;
}

export interface ShiftPlan {
  shift_id: string;
  start_time: string;
  end_time: string;
  start_elapsed_minutes: number;
  end_elapsed_minutes: number;
  handover_minutes: number;
  breaks: ShiftBreakWindow[];
}

export interface ShiftScheduleInfo {
  current_time_formatted: string;
  current_tick_minutes: number;
  shift_start_time: string;
  shift_end_time: string;
  break_start_time: string;
  break_end_time: string;
  operational_status: OperationalStatus;
  is_break_time: boolean;
  is_shift_ended: boolean;
  active_shift_id: string | null;
  is_handover_window: boolean;
}

export interface RealtimeMetrics {
  current_fatigue_level: number; // 0.0 - 1.0
  current_stress_level: number; // 0.0 - 1.0
  effective_throughput_per_hour: number;
  effective_error_probability: number; // 0.0 - 1.0
  burnout_hazard_risk: BurnoutRisk;
  throughput_multiplier: number;
}

export interface WorkerRuntimeSnapshot {
  worker_id: string;
  worker_name: string;
  assigned_job_id: string;
  assigned_step_id: string;
  shift_id: string;
  state: WorkerActivityState;
  compatibility_score: number;
  speed_factor: number;
  metrics: RealtimeMetrics;
}

export interface CurrentAssignment {
  worker_id: string;
  assigned_job_id: string;
  assigned_asset_id: string;
  calculated_realtime_metrics: RealtimeMetrics;
}

export interface SimulationSummary {
  total_output_units: number;
  target_output_units: number;
  production_achievement_percentage: number;
  total_operational_cost_idr: number;
  cost_per_unit_idr: number;
  efficiency_score: number; // 0 - 100
  total_human_errors?: number; 
  workers_at_risk?: number;
}

export interface MaterialInProcess {
  batch_code: string;
  material_name: string;
  quantity: number;              // Material mengantre (waiting to be processed)
  in_process_quantity?: number;  // Material yang sedang aktif diproses
  capacity: number;
  unit: string;
}

export interface StepBreakdown {
  step_id: string;
  step_name: string;
  status: StepStatus;
  output_generated: number;
  output_per_hour?: number;
  total_output_produced: number;
  operational_cost_idr: number;
  current_material: MaterialInProcess;
  speed_multiplier: number;
  wip_fill_pct: number;
  next_step_ids?: string[];
  depth?: number;
  branch_index?: number;
  worker_ids?: string[];
  defective_units?: number;
  downtime_ticks?: number;
  is_starved?: boolean;
}

export interface ActiveTransfer {
  from_step_id: string;
  to_step_id: string;
  batch_code: string;
  quantity: number;
  unit: string;
}

export interface WarehouseState {
  capacity: number;
  current_stock: number;
}

export interface WarehouseSource {
  warehouse_id: string;
  warehouse_name: string;
  material_name: string;
  material_unit: string;
  capacity: number;
  current_stock: number;
  supply_mode: 'finite' | 'continuous';
  target_step_ids: string[];
}

export interface OutputSinkState {
  output_id: string;
  output_name: string;
  material_name: string;
  material_unit: string;
  target_output_units: number;
  total_output_units: number;
  defective_units: number;
  achievement_percentage: number;
  source_step_ids: string[];
}

export interface StationErrorEvent {
  step_id: string;
  worker_id: string;
  tick_minutes: number;
  severity: 'low' | 'moderate' | 'high' | 'critical';
  rework_ticks: number;
  defective_units: number;
  downtime_ticks: number;
}

export const WAREHOUSE_STEP_ID = 'warehouse';

export interface LiveSimulationState {
  current_assignments: CurrentAssignment[];
  worker_runtime: WorkerRuntimeSnapshot[];
  system_bottlenecks: string[];
  warehouses: WarehouseSource[];
  outputs: OutputSinkState[];
  simulation_summary: SimulationSummary;
  step_breakdown: StepBreakdown[];
  active_transfers: ActiveTransfer[];
  recent_errors: StationErrorEvent[];
  analytical_insight_summary: string;
  shift_info: ShiftScheduleInfo;
}

export interface SimulationResponse {
  live_simulation_state: LiveSimulationState;
}

export function stepOrdinal(stepId: string): number {
  const suffix = stepId.match(/(\d+)(?!.*\d)/);
  return suffix ? Number(suffix[1]) : Number.MAX_SAFE_INTEGER;
}