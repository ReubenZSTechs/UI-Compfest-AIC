// features/simulation/types/simulation.types.ts
// Mirrors the `live_simulation_state` JSON contract produced by the RL engine.
// Keep in sync with digital-twin/types/digitalTwin.types.ts (worker_id / job_id / asset_id
// values here must resolve against Worker[] / JobDesk[] / Asset[] from that feature).

export type BurnoutRisk = 'low' | 'medium' | 'high';
export type StepStatus = 'normal' | 'bottleneck' | 'idle';
export type SimulationRunStatus = 'idle' | 'running' | 'paused' | 'completed';

export interface RealtimeMetrics {
  current_fatigue_level: number; // 0.0 - 1.0
  current_stress_level: number; // 0.0 - 1.0
  effective_throughput_per_hour: number;
  effective_error_probability: number; // 0.0 - 1.0
  burnout_hazard_risk: BurnoutRisk;
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
}

export interface StepBreakdown {
  step_id: string; // e.g. "step_07_baking" or "step_07"
  step_name: string;
  status: StepStatus;
  output_generated: number;
  operational_cost_idr: number;
}

export interface LiveSimulationState {
  current_assignments: CurrentAssignment[];
  system_bottlenecks: string[];
  simulation_summary: SimulationSummary;
  step_breakdown: StepBreakdown[];
  analytical_insight_summary: string;
}

export interface SimulationResponse {
  live_simulation_state: LiveSimulationState;
}

/** Extracts the leading step number ("step_07_baking" -> 7) so step_breakdown
 * entries can be matched against workflow_sequence / job_desks regardless of
 * naming drift between the two ("step_07" vs "step_07_baking"). */
export function stepOrdinal(stepId: string): number {
  const match = stepId.match(/step_(\d+)/);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}