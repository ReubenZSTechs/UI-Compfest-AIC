export type MetricDirection = "up" | "down";
export type StaffAction = "stay" | "moved";

export interface RlMetricComparison {
  before?: number | null;
  after: number;
  delta_pct?: number | null;
  direction?: MetricDirection | null;
  is_improvement?: boolean | null;
}

export interface RlScenarioMetrics {
  throughput_per_hour: RlMetricComparison;
  human_error_rate_pct: RlMetricComparison;
  total_op_cost_per_hour_rp: RlMetricComparison;
  cost_per_item_rp: RlMetricComparison;
  mean_fatigue: RlMetricComparison;
  max_fatigue: RlMetricComparison;
  bottleneck_count: RlMetricComparison;
}

export interface RlRewardWeights {
  throughput: number;
  cost: number;
  fatigue: number;
  bottleneck: number;
}

export interface RlScenarioConstraints {
  hiring_allowed: boolean;
  fire_or_mutation_allowed: boolean;
  automation_allowed: boolean;
  capex_rp: number;
  capex_used_rp: number;
}

export interface RlReallocationMove {
  move_id: string;
  worker_id: string;
  name: string;
  from_station?: string | null;
  to_station?: string | null;
  final_fatigue: number;
  final_stress: number;
}

export interface RlAssetUpgrade {
  asset_id: string;
  workflow_step?: string | null;
  is_automated: boolean;
  capex_rp: number;
}

export interface RlNewHire {
  worker_id: string;
  name: string;
  assigned_station?: string | null;
  capex_rp: number;
}

export interface RlStaffPosition {
  worker_id: string;
  name: string;
  current_station_rightnow?: string | null;
  optimal_station?: string | null;
  action: StaffAction;
  move_id?: string | null;
  projected_fatigue: number;
  projected_stress: number;
}

export interface RlFactoryFlowOptimal {
  reallocation_moves: RlReallocationMove[];
  asset_upgrades: RlAssetUpgrade[];
  new_hires: RlNewHire[];
  optimal_staff_positions: RlStaffPosition[];
  residual_bottleneck?: string | null;
}

export interface RlScenario {
  scenario_id: string;
  title: string;
  description: string;
  insight: string;
  recommended: boolean;
  reward_weights: RlRewardWeights;
  constraints: RlScenarioConstraints;
  metrics: RlScenarioMetrics;
  factory_flow_optimal: RlFactoryFlowOptimal;
  episode_reward: number;
}

export interface RlBundleMeta {
  status: string;
  algorithm: string;
  total_timesteps: number;
  factory_id?: string | null;
  recommended_scenario_id: string;
  baseline: {
    throughput_per_hour: number;
    human_error_rate_pct: number;
    cost_per_item_rp: number;
  };
}

export interface RlScenarioBundle {
  meta: RlBundleMeta;
  scenarios: RlScenario[];
}