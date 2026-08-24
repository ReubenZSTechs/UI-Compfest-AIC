// features/simulation/types/simulation.types.ts

export type BurnoutRisk = 'low' | 'medium' | 'high';
export type StepStatus = 'normal' | 'bottleneck' | 'idle';
export type SimulationRunStatus = 'idle' | 'running' | 'paused' | 'completed';
export type OperationalStatus = 'working' | 'break' | 'shift_ended';

export interface ShiftScheduleInfo {
  current_time_formatted: string; // e.g. "08:15", "12:30"
  current_tick_minutes: number;   // Total menit elapsed dari 0 (08:00)
  shift_start_time: string;       // "08:00"
  shift_end_time: string;         // "17:00"
  break_start_time: string;       // "12:00"
  break_end_time: string;         // "13:00"
  operational_status: OperationalStatus; // 'working' | 'break' | 'shift_ended'
  is_break_time: boolean;
  is_shift_ended: boolean;
}

export interface RealtimeMetrics {
  current_fatigue_level: number; // 0.0 - 1.0
  current_stress_level: number; // 0.0 - 1.0
  effective_throughput_per_hour: number;
  effective_error_probability: number; // 0.0 - 1.0
  burnout_hazard_risk: BurnoutRisk;
  throughput_multiplier: number;
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
  // --- TAMBAHAN BARU ---
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
  output_generated: number;      // Laju estimasi output per jam (backward compatibility)
  output_per_hour?: number;      // Laju estimasi output per jam
  total_output_produced: number; // Akumulasi TOTAL output node selama simulasi berjalan
  operational_cost_idr: number;
  current_material: MaterialInProcess;
  speed_multiplier: number;
  wip_fill_pct: number;
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

export const WAREHOUSE_STEP_ID = 'warehouse';

export interface LiveSimulationState {
  current_assignments: CurrentAssignment[];
  system_bottlenecks: string[];
  warehouse: WarehouseState;
  simulation_summary: SimulationSummary;
  step_breakdown: StepBreakdown[];
  active_transfers: ActiveTransfer[];
  analytical_insight_summary: string;
  shift_info: ShiftScheduleInfo; // Informasi Jam Kerja & Istirahat
}

export interface SimulationResponse {
  live_simulation_state: LiveSimulationState;
}

export function stepOrdinal(stepId: string): number {
  const match = stepId.match(/step_(\d+)/);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}