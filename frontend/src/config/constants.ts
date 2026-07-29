// ============================================
// Workflow / Digital Twin
// ============================================
export const WORKFLOW_STEPS = [
  "step_01_weighing",
  "step_02_mixing",
  "step_03_dough_dividing",
  "step_04_dough_shaping",
  "step_05_filling_panning",
  "step_06_proofing",
  "step_07_baking",
  "step_08_cooling",
  "step_09_sorting",
  "step_10_packaging",
] as const;

export type WorkflowStep = (typeof WORKFLOW_STEPS)[number];

// ============================================
// Human Factors / Ergonomics thresholds
// ============================================
export const FATIGUE_THRESHOLDS = {
  LOW: 0.3,
  MEDIUM: 0.6,
  HIGH: 0.8,
} as const;

export const STRESS_THRESHOLDS = {
  EUSTRESS_MAX: 0.5,
  DISTRESS_MIN: 0.5,
} as const;

export const BURNOUT_RISK_LEVELS = ["low", "medium", "high", "critical"] as const;
export type BurnoutRiskLevel = (typeof BURNOUT_RISK_LEVELS)[number];

// ============================================
// Simulation / RL
// ============================================
export const SIMULATION_STATUS = ["idle", "running", "paused", "converged", "error"] as const;
export type SimulationStatus = (typeof SIMULATION_STATUS)[number];

// Dipakai sebagai fallback selama WS belum ada (polling interval)
export const DEFAULT_POLLING_INTERVAL_MS = 2000;
export const WS_RECONNECT_DELAY_MS = 3000;
export const WS_MAX_RECONNECT_ATTEMPTS = 5;

// ============================================
// UI
// ============================================
export const DEBOUNCE_DELAY_MS = 300;
export const TOAST_DURATION_MS = 4000;

// ============================================
// Query Keys (React Query)
// ============================================
export const QUERY_KEYS = {
  DIGITAL_TWIN: "digital-twin",
  ASSETS: "assets",
  WORKERS: "workers",
  JOB_DESKS: "job-desks",
  COMPATIBILITY_MATRIX: "compatibility-matrix",
  SIMULATION_STATE: "simulation-state",
  SIMULATION_SCENARIOS: "simulation-scenarios",
} as const;