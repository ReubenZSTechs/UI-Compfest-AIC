// Real API — fetch config sekali dari backend, lalu jalankan tick loop lokal.
// Tick logic di file ini SENGAJA identik dengan `simulationApi.mock.ts` kamu;
// bedanya cuma satu: semua tabel/kapasitas/worker seed sekarang datang dari
// GET /api/v1/factories/:factoryId/simulation-config, bukan hardcoded di file ini.
//
// Update: engine sekarang graph-driven (routing antar step lewat station_edges /
// entry_ordinals / terminal_ordinals dari config), bukan lagi rantai linear 1..10.
// Update: physics-backed worker engine dengan fatigue, stress, dan real-time errors.

import type {
  ActiveTransfer,
  BurnoutRisk,
  MaterialInProcess,
  OperationalStatus,
  ShiftScheduleInfo,
  SimulationResponse,
  StationErrorEvent,
  StepBreakdown,
} from '../types/simulation.types';
import { API_BASE_URL } from '../../../config/env';

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const jitter = (value: number, amount: number, min: number, max: number) =>
  Number(clamp(value + (Math.random() - 0.5) * amount, min, max).toFixed(4));
const round2 = (value: number) => Number(value.toFixed(2));

// ---------------------------------------------------------------------------
// Physics Engine Constants & Interfaces
// ---------------------------------------------------------------------------

const PHYSICAL_WEIGHT: Record<string, number> = { low: 0.7, medium: 1.0, high: 1.35 };
const ERROR_CONSEQUENCE: Record<
  string,
  { reworkCycles: number; scrapRatio: number; downtimeTicks: number }
> = {
  low: { reworkCycles: 0.25, scrapRatio: 0.02, downtimeTicks: 0 },
  moderate: { reworkCycles: 0.5, scrapRatio: 0.05, downtimeTicks: 0 },
  high: { reworkCycles: 1.0, scrapRatio: 0.12, downtimeTicks: 1 },
  critical: { reworkCycles: 1.5, scrapRatio: 0.25, downtimeTicks: 3 },
};

const BASE_SPEED_FLOOR = 0.55;
const BASE_SPEED_SPAN = 0.65;
const EXPERIENCE_CAP = 0.15;
const EXPERIENCE_DIVISOR = 40;
const FATIGUE_SPEED_PENALTY = 0.45;
const STRESS_SPEED_PENALTY = 0.2;
const HANDOVER_SPEED_FACTOR = 0.5;
const REWORK_SPEED_FACTOR = 0.65;
const FATIGUE_PER_MINUTE = 0.0016;
const STRESS_PER_MINUTE = 0.0011;
const BREAK_RECOVERY_PER_MINUTE = 0.0045;
const IDLE_RECOVERY_RATIO = 0.4;
const COLLABORATION_CONGESTION = 0.12;
const BASE_ERROR_RATE = 0.004;

export type WorkerActivityState = 'active' | 'idle' | 'on_break' | 'off_shift' | 'handover' | 'rework';

export interface WorkerRuntimeProfile {
  worker_id: string;
  name: string;
  skills: string[];
  years_of_experience: number;
  cognitive_resilience: number;
  baseline_physical_stamina: number;
  compatibility_by_job_id: Record<string, number>;
}

export interface JobDemandProfile {
  job_id: string;
  required_skills: string[];
  required_cognitive_focus: number;
  physical_demand_level: string;
  physical_strain_index: number;
  task_complexity: number;
  error_severity: string;
}

interface WorkerRuntime {
  workerId: string;
  workerName: string;
  jobId: string;
  ordinal: number;
  shiftId: string;
  fatigue: number;
  stress: number;
  compatibility: number;
  state: WorkerActivityState;
  speedFactor: number;
  reworkTicksRemaining: number;
}

// ---------------------------------------------------------------------------
// Engine state (module-scoped persistence)
// ---------------------------------------------------------------------------

const workerRuntimeById: Record<string, WorkerRuntime> = {};
const downtimeByOrdinal: Record<number, number> = {};
const defectiveByOrdinal: Record<number, number> = {};
const outputTotals: Record<string, { good: number; defective: number }> = {};
const recentErrors: StationErrorEvent[] = [];

let warehouseStates: any[] = [];
let batchSeq = 0;
let finishedGoodsTotal = 0;
let currentTickMinutes = 0;
const materialByOrdinal: Record<number, MaterialInProcess> = {};
const batchStateByOrdinal: Record<number, BatchState> = {};
const totalOutputByOrdinal: Record<number, number> = {};
const routingCursor: Record<number, number> = {};
let engineInitialized = false;

// ---------------------------------------------------------------------------
// Config types — bentuk response dari backend
// ---------------------------------------------------------------------------

interface MaterialTemplate {
  name: string;
  unit: string;
}

interface SimulationConfig {
  materials_by_ordinal: Record<number, MaterialTemplate>;
  step_names: Record<number, string>;
  step_cost_base: Record<number, number>;
  capacity_by_ordinal: Record<number, number>;
  batch_in_by_ordinal: Record<number, number>;
  batch_out_by_ordinal: Record<number, number>;
  cycle_ticks_by_ordinal: Record<number, number>;
  step_ids_by_ordinal: Record<number, string>;
  station_edges: Record<number, number[]>;
  entry_ordinals: number[];
  terminal_ordinals: number[];
  ordinal_by_job_id: Record<string, number>;
  bottleneck_fill_threshold: number;
  idle_qty_threshold: number;
  station_1_safety_margin: number;
  
  warehouses: any[]; // Extended for multi-source
  outputs: any[];    // Extended for multi-sink

  worker_profiles: WorkerRuntimeProfile[];
  job_demands: JobDemandProfile[];
  shift_plans: {
    shift_id: string;
    start_elapsed_minutes: number;
    end_elapsed_minutes: number;
    handover_minutes: number;
    breaks: { start_elapsed_minutes: number; end_elapsed_minutes: number }[];
  }[];
  shift_roster: { shift_id: string; job_id: string; ordinal: number; worker_ids: string[] }[];

  worker_throughput_multiplier: Record<string, number>;
  shift_start_minutes: number;
  break_start_elapsed: number;
  break_end_elapsed: number;
  shift_end_elapsed: number;
  analytical_insight_summary: string;
  target_output_units: number;
  initial_batch_seq: number;
}

interface BatchState {
  ticksRemaining: number;
  inProgressBatchCode: string | null;
  inProgressQty: number;
  readyToShip: { qty: number; batchCode: string } | null;
}

// ---------------------------------------------------------------------------
// Config Scoping & Fetching
// ---------------------------------------------------------------------------

let configPromise: Promise<SimulationConfig> | null = null;
let configFactoryId: string | null = null;

export function setSimulationFactoryId(factoryId: string | null): void {
  if (factoryId !== configFactoryId) {
    configFactoryId = factoryId;
    configPromise = null;
  }
}

async function loadConfig(): Promise<SimulationConfig> {
  if (!configFactoryId) {
    throw new Error("factoryId simulasi belum ditentukan.");
  }
  if (!configPromise) {
    const url = `${API_BASE_URL}/factories/${configFactoryId}/simulation-config`;
    configPromise = fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Gagal memuat konfigurasi simulasi (${res.status})`);
        return res.json() as Promise<SimulationConfig>;
      })
      .catch((err) => {
        configPromise = null;
        throw err;
      });
  }
  return configPromise;
}

export async function getSimulationConfig(): Promise<SimulationConfig> {
  return loadConfig();
}

function ensureEngineInitialized(config: SimulationConfig) {
  if (engineInitialized) return;
  engineInitialized = true;
  batchSeq = config.initial_batch_seq;
  warehouseStates = config.warehouses ? JSON.parse(JSON.stringify(config.warehouses)) : [];
}

function nextBatchCode(): string {
  batchSeq += 1;
  return `#B-${batchSeq}`;
}

function ensureInitialized(ordinal: number, config: SimulationConfig) {
  if (!materialByOrdinal[ordinal]) {
    const template = config.materials_by_ordinal[ordinal];
    materialByOrdinal[ordinal] = {
      batch_code: nextBatchCode(),
      material_name: template.name,
      quantity: 0,
      in_process_quantity: 0,
      capacity: config.capacity_by_ordinal[ordinal],
      unit: template.unit,
    };
  }
  if (!batchStateByOrdinal[ordinal]) {
    batchStateByOrdinal[ordinal] = {
      ticksRemaining: 0,
      inProgressBatchCode: null,
      inProgressQty: 0,
      readyToShip: null,
    };
  }
}

export function resetMockSimulationState(config: SimulationConfig) {
  engineInitialized = true;
  batchSeq = config.initial_batch_seq;
  finishedGoodsTotal = 0;
  currentTickMinutes = 0;
  warehouseStates = config.warehouses ? JSON.parse(JSON.stringify(config.warehouses)) : [];
  
  Object.keys(materialByOrdinal).forEach((k) => delete materialByOrdinal[Number(k)]);
  Object.keys(batchStateByOrdinal).forEach((k) => delete batchStateByOrdinal[Number(k)]);
  Object.keys(totalOutputByOrdinal).forEach((k) => delete totalOutputByOrdinal[Number(k)]);
  Object.keys(routingCursor).forEach((k) => delete routingCursor[Number(k)]);

  // Clear new state
  Object.keys(workerRuntimeById).forEach((k) => delete workerRuntimeById[k]);
  Object.keys(downtimeByOrdinal).forEach((k) => delete downtimeByOrdinal[Number(k)]);
  Object.keys(defectiveByOrdinal).forEach((k) => delete defectiveByOrdinal[Number(k)]);
  Object.keys(outputTotals).forEach((k) => delete outputTotals[k]);
  recentErrors.length = 0;
}

function riskFromLevels(fatigue: number, stress: number): BurnoutRisk {
  if (fatigue > 0.65 || stress > 0.55) return 'high';
  if (fatigue > 0.4 || stress > 0.35) return 'medium';
  return 'low';
}

// ---------------------------------------------------------------------------
// Physics Engine & Worker Logic
// ---------------------------------------------------------------------------

function skillMatchRatio(skills: string[], required: string[]): number {
  if (required.length === 0) return 0.5;
  const owned = new Set(
    skills.flatMap((skill) => skill.toLowerCase().split(/\s+/).filter(Boolean))
  );
  const matched = required.filter((entry) =>
    entry
      .toLowerCase()
      .split(/\s+/)
      .some((token) => owned.has(token))
  ).length;
  return matched / required.length;
}

function resolveCompatibility(
  profile: WorkerRuntimeProfile,
  demand: JobDemandProfile
): number {
  const declared = profile.compatibility_by_job_id?.[demand.job_id];
  if (typeof declared === "number") return clamp(declared, 0, 1);
  const skillComponent = skillMatchRatio(profile.skills, demand.required_skills);
  const experienceComponent = clamp(profile.years_of_experience / 15, 0, 1);
  const resilienceGap = clamp(
    1 - Math.abs(demand.required_cognitive_focus - profile.cognitive_resilience),
    0,
    1
  );
  const staminaGap = clamp(
    1 -
      Math.abs((PHYSICAL_WEIGHT[demand.physical_demand_level] ?? 1) - 1) +
      (profile.baseline_physical_stamina - 0.5),
    0,
    1
  );
  return clamp(
    0.4 * skillComponent +
      0.25 * experienceComponent +
      0.2 * resilienceGap +
      0.15 * staminaGap,
    0,
    1
  );
}

function workerSpeedFactor(
  runtime: WorkerRuntime,
  profile: WorkerRuntimeProfile
): number {
  if (runtime.state === "idle" || runtime.state === "on_break" || runtime.state === "off_shift") {
    return 0;
  }
  const base = BASE_SPEED_FLOOR + BASE_SPEED_SPAN * runtime.compatibility;
  const experienceBonus = Math.min(
    EXPERIENCE_CAP,
    profile.years_of_experience / EXPERIENCE_DIVISOR
  );
  let speed =
    (base + experienceBonus) *
    (1 - FATIGUE_SPEED_PENALTY * runtime.fatigue) *
    (1 - STRESS_SPEED_PENALTY * runtime.stress);
  
  if (runtime.state === "handover") speed *= HANDOVER_SPEED_FACTOR;
  if (runtime.state === "rework") speed *= REWORK_SPEED_FACTOR;
  return clamp(speed, 0.15, 2.5);
}

function aggregateStationSpeed(speeds: number[]): number {
  const active = speeds.filter((speed) => speed > 0).sort((a, b) => b - a);
  if (active.length === 0) return 0;
  return active.reduce(
    (total, speed, rank) => total + speed / (1 + COLLABORATION_CONGESTION * rank),
    0
  );
}

function advanceFatigue(
  runtime: WorkerRuntime,
  profile: WorkerRuntimeProfile,
  demand: JobDemandProfile,
  minutes: number
): number {
  if (runtime.state === "on_break" || runtime.state === "off_shift") {
    return clamp(runtime.fatigue - BREAK_RECOVERY_PER_MINUTE * minutes, 0, 1);
  }
  if (runtime.state === "idle") {
    return clamp(
      runtime.fatigue - BREAK_RECOVERY_PER_MINUTE * IDLE_RECOVERY_RATIO * minutes,
      0,
      1
    );
  }
  const physicalWeight = PHYSICAL_WEIGHT[demand.physical_demand_level] ?? 1;
  const staminaGap = clamp(1.6 - profile.baseline_physical_stamina, 0.5, 1.6);
  const strainMultiplier = 1 + 0.5 * clamp(demand.physical_strain_index, 0, 1);
  return clamp(
    runtime.fatigue +
      FATIGUE_PER_MINUTE * physicalWeight * staminaGap * strainMultiplier * minutes,
    0,
    1
  );
}

function advanceStress(
  runtime: WorkerRuntime,
  profile: WorkerRuntimeProfile,
  demand: JobDemandProfile,
  minutes: number,
  queuePressure: number
): number {
  if (
    runtime.state === "on_break" ||
    runtime.state === "off_shift" ||
    runtime.state === "idle"
  ) {
    return clamp(
      runtime.stress - BREAK_RECOVERY_PER_MINUTE * IDLE_RECOVERY_RATIO * minutes,
      0,
      1
    );
  }
  const resilienceGap = clamp(1 - profile.cognitive_resilience, 0.05, 1);
  return clamp(
    runtime.stress +
      STRESS_PER_MINUTE *
        demand.required_cognitive_focus *
        resilienceGap *
        (1 + clamp(queuePressure, 0, 1)) *
        minutes,
    0,
    1
  );
}

function errorProbability(
  runtime: WorkerRuntime,
  demand: JobDemandProfile
): number {
  return clamp(
    BASE_ERROR_RATE *
      (1 + 1.8 * runtime.fatigue) *
      (1 + 1.2 * runtime.stress) *
      (1 + demand.task_complexity) *
      (1 - 0.5 * runtime.compatibility),
    0,
    0.45
  );
}

function resolveWorkerState(
  isOnShift: boolean,
  isBreak: boolean,
  isHandover: boolean,
  hasMaterial: boolean,
  isReworking: boolean
): WorkerActivityState {
  if (!isOnShift) return "off_shift";
  if (isBreak) return "on_break";
  if (isHandover) return "handover";
  if (isReworking) return "rework";
  if (!hasMaterial) return "idle";
  return "active";
}

function activeShiftFor(elapsedMinutes: number, config: SimulationConfig) {
  return (
    config.shift_plans?.find(
      (plan) =>
        elapsedMinutes >= plan.start_elapsed_minutes &&
        elapsedMinutes < plan.end_elapsed_minutes
    ) ?? null
  );
}

function isHandoverWindow(elapsedMinutes: number, config: SimulationConfig): boolean {
  return (config.shift_plans || []).some((plan) => {
    const enteringWindow =
      elapsedMinutes >= plan.start_elapsed_minutes &&
      elapsedMinutes < plan.start_elapsed_minutes + plan.handover_minutes;
    const leavingWindow =
      elapsedMinutes >= plan.end_elapsed_minutes - plan.handover_minutes &&
      elapsedMinutes < plan.end_elapsed_minutes;
    return enteringWindow || leavingWindow;
  });
}

function isBreakWindow(elapsedMinutes: number, shiftId: string | null, config: SimulationConfig) {
  const plan = (config.shift_plans || []).find((item) => item.shift_id === shiftId);
  if (!plan) return false;
  return plan.breaks.some(
    (window) =>
      elapsedMinutes >= window.start_elapsed_minutes &&
      elapsedMinutes < window.end_elapsed_minutes
  );
}

function syncWorkerRuntime(config: SimulationConfig, elapsedMinutes: number): void {
  const shift = activeShiftFor(elapsedMinutes, config);
  const rosterForShift = (config.shift_roster || []).filter(
    (entry) => entry.shift_id === (shift?.shift_id ?? "")
  );
  const profileById = new Map((config.worker_profiles || []).map((item) => [item.worker_id, item]));
  const demandByJobId = new Map((config.job_demands || []).map((item) => [item.job_id, item]));
  
  for (const entry of rosterForShift) {
    for (const workerId of entry.worker_ids) {
      if (workerRuntimeById[workerId]) continue;
      const profile = profileById.get(workerId);
      const demand = demandByJobId.get(entry.job_id);
      if (!profile || !demand) continue;
      workerRuntimeById[workerId] = {
        workerId,
        workerName: profile.name || workerId,
        jobId: entry.job_id,
        ordinal: entry.ordinal,
        shiftId: entry.shift_id,
        fatigue: 0.08,
        stress: 0.06,
        compatibility: resolveCompatibility(profile, demand),
        state: "active",
        speedFactor: 0,
        reworkTicksRemaining: 0,
      };
    }
  }
}

function updateWorkerRuntime(
  config: SimulationConfig,
  elapsedMinutes: number,
  isStationIdleMap: Record<number, boolean>,
  wipFillByOrdinal: Record<number, number>
): void {
  const shift = activeShiftFor(elapsedMinutes, config);
  const handover = isHandoverWindow(elapsedMinutes, config);
  const onBreak = isBreakWindow(elapsedMinutes, shift?.shift_id ?? null, config);
  const profileById = new Map((config.worker_profiles || []).map((item) => [item.worker_id, item]));
  const demandByJobId = new Map((config.job_demands || []).map((item) => [item.job_id, item]));
  
  for (const runtime of Object.values(workerRuntimeById)) {
    const profile = profileById.get(runtime.workerId);
    const demand = demandByJobId.get(runtime.jobId);
    if (!profile || !demand) continue;
    
    const isOnShift = runtime.shiftId === (shift?.shift_id ?? "");
    const hasMaterial = !(isStationIdleMap[runtime.ordinal] ?? true);
    const isReworking = runtime.reworkTicksRemaining > 0;
    
    runtime.state = resolveWorkerState(isOnShift, onBreak, handover, hasMaterial, isReworking);
    runtime.fatigue = advanceFatigue(runtime, profile, demand, 1);
    runtime.stress = advanceStress(
      runtime,
      profile,
      demand,
      1,
      wipFillByOrdinal[runtime.ordinal] ?? 0
    );
    runtime.speedFactor = workerSpeedFactor(runtime, profile);
    
    if (isReworking) {
      runtime.reworkTicksRemaining = Math.max(0, runtime.reworkTicksRemaining - 1);
    }
  }
}

function calculateSpeedByOrdinal(config: SimulationConfig): Record<number, number> {
  const grouped: Record<number, number[]> = {};
  for (const runtime of Object.values(workerRuntimeById)) {
    grouped[runtime.ordinal] = [...(grouped[runtime.ordinal] ?? []), runtime.speedFactor];
  }
  const speedByOrdinal: Record<number, number> = {};
  for (const ordinal of stationOrdinals(config)) {
    const speeds = grouped[ordinal] ?? [];
    const aggregated = aggregateStationSpeed(speeds);
    speedByOrdinal[ordinal] = aggregated > 0 ? aggregated : speeds.length === 0 ? 1 : 0.05;
  }
  return speedByOrdinal;
}

function resolveCycleErrors(
  ordinal: number,
  outputQty: number,
  config: SimulationConfig,
  elapsedMinutes: number
): { goodUnits: number; defectiveUnits: number } {
  const demandByJobId = new Map((config.job_demands || []).map((item) => [item.job_id, item]));
  const stationWorkers = Object.values(workerRuntimeById).filter(
    (runtime) => runtime.ordinal === ordinal && runtime.state === "active"
  );
  
  let goodUnits = outputQty;
  let defectiveUnits = 0;
  
  for (const runtime of stationWorkers) {
    const demand = demandByJobId.get(runtime.jobId);
    if (!demand) continue;
    
    if (Math.random() > errorProbability(runtime, demand)) continue;
    
    const consequence = ERROR_CONSEQUENCE[demand.error_severity] ?? ERROR_CONSEQUENCE.moderate;
    const scrapped = round2(goodUnits * consequence.scrapRatio);
    goodUnits = round2(goodUnits - scrapped);
    defectiveUnits = round2(defectiveUnits + scrapped);
    
    runtime.reworkTicksRemaining = Math.max(
      runtime.reworkTicksRemaining,
      Math.ceil(consequence.reworkCycles * (config.cycle_ticks_by_ordinal[ordinal] || 1))
    );
    runtime.stress = clamp(runtime.stress + 0.06, 0, 1);
    downtimeByOrdinal[ordinal] = (downtimeByOrdinal[ordinal] ?? 0) + consequence.downtimeTicks;
    
    recentErrors.unshift({
      step_id: stepIdFor(ordinal, config),
      worker_id: runtime.workerId,
      tick_minutes: elapsedMinutes,
      severity: demand.error_severity as StationErrorEvent["severity"],
      rework_ticks: runtime.reworkTicksRemaining,
      defective_units: scrapped,
      downtime_ticks: consequence.downtimeTicks,
    });
    recentErrors.splice(12);
  }
  
  defectiveByOrdinal[ordinal] = round2((defectiveByOrdinal[ordinal] ?? 0) + defectiveUnits);
  return { goodUnits, defectiveUnits };
}

// ---------------------------------------------------------------------------
// Graph & Helpers
// ---------------------------------------------------------------------------

function stationOrdinals(config: SimulationConfig): number[] {
  return Object.keys(config.step_names)
    .map(Number)
    .filter((ordinal) => Number.isFinite(ordinal))
    .sort((a, b) => a - b);
}

function stepIdFor(ordinal: number, config: SimulationConfig): string {
  return config.step_ids_by_ordinal[ordinal] ?? `step_${String(ordinal).padStart(2, '0')}`;
}

function successorsOf(ordinal: number, config: SimulationConfig): number[] {
  return config.station_edges[ordinal] ?? [];
}

function pickDestination(
  ordinal: number,
  quantity: number,
  config: SimulationConfig
): number | null {
  const targets = successorsOf(ordinal, config);
  if (targets.length === 0) return null;

  const start = routingCursor[ordinal] ?? 0;
  for (let offset = 0; offset < targets.length; offset += 1) {
    const candidate = targets[(start + offset) % targets.length];
    const dest = materialByOrdinal[candidate];
    if (!dest) continue;
    const spare = config.capacity_by_ordinal[candidate] - dest.quantity;
    if (quantity <= spare + 1e-9) {
      routingCursor[ordinal] = (start + offset + 1) % targets.length;
      return candidate;
    }
  }
  return null;
}

function effectiveCycleTicks(ordinal: number, speed: number, config: SimulationConfig): number {
  return Math.max(1, Math.round(config.cycle_ticks_by_ordinal[ordinal] / speed));
}

function calculateShiftInfo(elapsedMinutes: number, config: SimulationConfig): ShiftScheduleInfo {
  const currentTotalMins = config.shift_start_minutes + elapsedMinutes;
  const hours = Math.floor(currentTotalMins / 60) % 24;
  const mins = currentTotalMins % 60;
  const timeFormatted = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;
  
  const isBreak = elapsedMinutes >= config.break_start_elapsed && elapsedMinutes < config.break_end_elapsed;
  const isShiftEnded = elapsedMinutes >= config.shift_end_elapsed;
  
  let operationalStatus: OperationalStatus = 'working';
  if (isShiftEnded) operationalStatus = 'shift_ended';
  else if (isBreak) operationalStatus = 'break';
  
  const fmt = (mins: number) => {
    const total = config.shift_start_minutes + mins;
    return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  };
  
  const activeShift = activeShiftFor(elapsedMinutes, config);
  
  return {
    current_time_formatted: timeFormatted,
    current_tick_minutes: elapsedMinutes,
    shift_start_time: fmt(0),
    shift_end_time: fmt(config.shift_end_elapsed),
    break_start_time: fmt(config.break_start_elapsed),
    break_end_time: fmt(config.break_end_elapsed),
    operational_status: operationalStatus,
    is_break_time: isBreak,
    is_shift_ended: isShiftEnded,
    active_shift_id: activeShift?.shift_id ?? null,
    is_handover_window: isHandoverWindow(elapsedMinutes, config),
  };
}

function statusFor(
  waitingQty: number,
  inProcessQty: number,
  capacity: number,
  ordinal: number,
  config: SimulationConfig
): 'idle' | 'bottleneck' | 'normal' {
  const totalWip = waitingQty + inProcessQty;
  if (totalWip <= config.idle_qty_threshold) return 'idle';
  if (config.entry_ordinals.includes(ordinal)) return 'normal';
  if (totalWip / capacity >= config.bottleneck_fill_threshold) return 'bottleneck';
  return 'normal';
}

function outputSinksFor(ordinal: number, config: SimulationConfig): any[] {
  const stepId = stepIdFor(ordinal, config);
  return (config.outputs || []).filter((sink) => sink.source_step_id === stepId);
}

function buildOutputStates(config: SimulationConfig): any[] {
  return (config.outputs || []).map((sink) => ({
    ...sink,
    good_units: outputTotals[sink.output_id]?.good ?? 0,
    defective_units: outputTotals[sink.output_id]?.defective ?? 0,
  }));
}

function buildStepBreakdown(
  speedByOrdinal: Record<number, number>,
  config: SimulationConfig
): StepBreakdown[] {
  return stationOrdinals(config).map((ordinal) => {
    const material = materialByOrdinal[ordinal];
    const batchState = batchStateByOrdinal[ordinal];

    const waitingQty = material.quantity;
    const inProcessQty = batchState?.inProgressQty ?? 0;
    const totalWip = waitingQty + inProcessQty;

    const speed = speedByOrdinal[ordinal] ?? 1;
    const status = statusFor(waitingQty, inProcessQty, material.capacity, ordinal, config);

    const nominalRatePerHour = Number(
      (
        (config.batch_out_by_ordinal[ordinal] / config.cycle_ticks_by_ordinal[ordinal]) *
        speed *
        12
      ).toFixed(1)
    );

    return {
      step_id: stepIdFor(ordinal, config),
      step_name: config.step_names[ordinal],
      status,
      output_generated: nominalRatePerHour,
      output_per_hour: nominalRatePerHour,
      total_output_produced: round2(totalOutputByOrdinal[ordinal] ?? 0),
      operational_cost_idr: config.step_cost_base[ordinal],
      current_material: {
        ...material,
        quantity: waitingQty,
        in_process_quantity: inProcessQty,
      },
      speed_multiplier: Number(speed.toFixed(2)),
      wip_fill_pct: Number(((totalWip / material.capacity) * 100).toFixed(1)),
      next_step_ids: successorsOf(ordinal, config).map((target) => stepIdFor(target, config)),
      
      // New layout and worker fields
      worker_ids: Object.values(workerRuntimeById)
        .filter((runtime) => runtime.ordinal === ordinal)
        .map((runtime) => runtime.workerId),
      defective_units: round2(defectiveByOrdinal[ordinal] ?? 0),
      downtime_ticks: downtimeByOrdinal[ordinal] ?? 0,
      is_starved: (batchStateByOrdinal[ordinal]?.ticksRemaining ?? 0) === 0 &&
        materialByOrdinal[ordinal].quantity + 1e-9 < config.batch_in_by_ordinal[ordinal],
    };
  });
}

let efficiencyScore = 78.5;

export async function getSeedSimulationState(): Promise<SimulationResponse> {
  const config = await loadConfig();
  ensureEngineInitialized(config);
  for (const ordinal of stationOrdinals(config)) ensureInitialized(ordinal, config);

  syncWorkerRuntime(config, currentTickMinutes);
  const speedByOrdinal = calculateSpeedByOrdinal(config);
  const step_breakdown = buildStepBreakdown(speedByOrdinal, config);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);

  return {
    live_simulation_state: {
      current_assignments: [], // Deprecated by worker_runtime payload
      system_bottlenecks,
      simulation_summary: {
        total_output_units: finishedGoodsTotal,
        target_output_units: config.target_output_units,
        production_achievement_percentage: Number(((finishedGoodsTotal / config.target_output_units) * 100).toFixed(1)),
        total_operational_cost_idr,
        cost_per_unit_idr: 0,
        efficiency_score: efficiencyScore,
      },
      step_breakdown,
      active_transfers: [],
      analytical_insight_summary: config.analytical_insight_summary,
      shift_info: calculateShiftInfo(currentTickMinutes, config),
      
      // New payloads
      worker_runtime: [],
      warehouses: warehouseStates,
      outputs: buildOutputStates(config),
      recent_errors: [...recentErrors],
    },
  };
}

export async function fetchLiveSimulationState(previous?: SimulationResponse): Promise<SimulationResponse> {
  const config = await loadConfig();
  ensureEngineInitialized(config);
  await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 200));

  const source = previous ?? (await getSeedSimulationState());
  for (const ordinal of stationOrdinals(config)) ensureInitialized(ordinal, config);

  if (previous) currentTickMinutes += 1;
  const shiftInfo = calculateShiftInfo(currentTickMinutes, config);
  
  syncWorkerRuntime(config, currentTickMinutes);
  
  const isStationIdleMap: Record<number, boolean> = {};
  const wipFillByOrdinal: Record<number, number> = {};
  
  for (const ordinal of stationOrdinals(config)) {
    const batchState = batchStateByOrdinal[ordinal];
    const material = materialByOrdinal[ordinal];
    const batchIn = config.batch_in_by_ordinal[ordinal];
    isStationIdleMap[ordinal] = batchState.ticksRemaining === 0 && material.quantity + 1e-9 < batchIn;
    wipFillByOrdinal[ordinal] = (material.quantity + batchState.inProgressQty) / (material.capacity || 1);
  }

  updateWorkerRuntime(config, currentTickMinutes, isStationIdleMap, wipFillByOrdinal);
  const speedByOrdinal = calculateSpeedByOrdinal(config);
  const activeTransfers: ActiveTransfer[] = [];

  const ordinalByStepId = Object.fromEntries(
    Object.entries(config.step_ids_by_ordinal).map(([k, v]) => [v, Number(k)])
  );

  if (!shiftInfo.is_break_time && !shiftInfo.is_shift_ended) {
    const ordinals = stationOrdinals(config);

    // 1) SHIP PHASE
    for (const ordinal of ordinals) {
      const batchState = batchStateByOrdinal[ordinal];
      const pending = batchState.readyToShip;
      if (!pending) continue;

      const sinks = outputSinksFor(ordinal, config);
      if (sinks.length > 0) {
        const share = pending.qty / sinks.length;
        for (const sink of sinks) {
          const bucket = outputTotals[sink.output_id] ?? { good: 0, defective: 0 };
          bucket.good = round2(bucket.good + share);
          outputTotals[sink.output_id] = bucket;
          activeTransfers.push({
            from_step_id: stepIdFor(ordinal, config),
            to_step_id: sink.output_id,
            batch_code: pending.batchCode,
            quantity: round2(share),
            unit: sink.material_unit,
          });
        }
        finishedGoodsTotal = round2(finishedGoodsTotal + pending.qty);
        batchState.readyToShip = null;
        continue;
      }

      const destOrdinal = pickDestination(ordinal, pending.qty, config);
      if (destOrdinal === null) continue;

      const dest = materialByOrdinal[destOrdinal];
      dest.quantity = round2(dest.quantity + pending.qty);
      dest.batch_code = pending.batchCode;
      activeTransfers.push({
        from_step_id: stepIdFor(ordinal, config),
        to_step_id: stepIdFor(destOrdinal, config),
        batch_code: pending.batchCode,
        quantity: pending.qty,
        unit: config.materials_by_ordinal[destOrdinal].unit,
      });
      batchState.readyToShip = null;
    }

    // 2) CYCLE-COMPLETION PHASE
    for (const ordinal of ordinals) {
      const batchState = batchStateByOrdinal[ordinal];
      if (batchState.ticksRemaining <= 0) continue;

      batchState.ticksRemaining -= 1;
      if (batchState.ticksRemaining === 0) {
        const outputQty = config.batch_out_by_ordinal[ordinal];
        
        // Error resolution replaces perfect output
        const { goodUnits } = resolveCycleErrors(ordinal, outputQty, config, currentTickMinutes);

        batchState.readyToShip = {
          qty: goodUnits,
          batchCode: batchState.inProgressBatchCode ?? nextBatchCode(),
        };

        totalOutputByOrdinal[ordinal] = round2((totalOutputByOrdinal[ordinal] ?? 0) + goodUnits);

        batchState.inProgressBatchCode = null;
        batchState.inProgressQty = 0;
      }
    }

    // 3) START PHASE
    for (const ordinal of ordinals) {
      const batchState = batchStateByOrdinal[ordinal];
      if (batchState.ticksRemaining > 0 || batchState.readyToShip) continue;

      const material = materialByOrdinal[ordinal];
      const batchIn = config.batch_in_by_ordinal[ordinal];
      if (material.quantity + 1e-9 < batchIn) continue;

      material.quantity = round2(material.quantity - batchIn);
      batchState.ticksRemaining = effectiveCycleTicks(ordinal, speedByOrdinal[ordinal] ?? 1, config);
      batchState.inProgressBatchCode = nextBatchCode();
      batchState.inProgressQty = batchIn;
    }

    // 4) WAREHOUSES -> ENTRY STATIONS feed (multi-source)
    for (const source of warehouseStates) {
      const targets = (source.target_step_ids || [])
        .map((stepId: string) => ordinalByStepId[stepId])
        .filter((ordinal: number | undefined) => ordinal !== undefined);
      if (targets.length === 0) continue;
      
      const feedPerTarget = source.feed_rate / targets.length;
      for (const targetOrdinal of targets) {
        const station = materialByOrdinal[targetOrdinal];
        if (!station) continue;
        
        const safeCeiling =
          (config.bottleneck_fill_threshold - config.station_1_safety_margin) *
          config.capacity_by_ordinal[targetOrdinal];
        const safeSpare = Math.max(0, safeCeiling - station.quantity);
        const feed = Math.max(0, Math.min(feedPerTarget, source.current_stock, safeSpare));
        
        if (feed <= 0.05) continue;
        
        source.current_stock =
          source.supply_mode === "continuous"
            ? source.capacity
            : round2(source.current_stock - feed);
        station.quantity = round2(station.quantity + feed);
        
        activeTransfers.push({
          from_step_id: source.warehouse_id,
          to_step_id: stepIdFor(targetOrdinal, config),
          batch_code: station.batch_code,
          quantity: round2(feed),
          unit: source.material_unit,
        });
      }
      
      if (source.supply_mode === "finite" && source.replenish_per_tick > 0) {
        source.current_stock = round2(
          Math.min(source.capacity, source.current_stock + source.replenish_per_tick)
        );
      }
    }
  }

  const step_breakdown = buildStepBreakdown(speedByOrdinal, config);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);
  const roundedOutput = round2(finishedGoodsTotal);
  const targetOutput = source.live_simulation_state.simulation_summary.target_output_units;

  efficiencyScore = jitter(source.live_simulation_state.simulation_summary.efficiency_score, 3, 40, 98);

  return {
    live_simulation_state: {
      current_assignments: [], // Deprecated block
      system_bottlenecks,
      step_breakdown,
      active_transfers: activeTransfers,
      simulation_summary: {
        total_output_units: roundedOutput,
        target_output_units: targetOutput,
        production_achievement_percentage: Number(((roundedOutput / targetOutput) * 100).toFixed(1)),
        total_operational_cost_idr,
        cost_per_unit_idr: roundedOutput > 0 ? Number((total_operational_cost_idr / roundedOutput).toFixed(2)) : 0,
        efficiency_score: efficiencyScore,
      },
      analytical_insight_summary: source.live_simulation_state.analytical_insight_summary,
      shift_info: shiftInfo,
      
      // New payloads
      worker_runtime: Object.values(workerRuntimeById).map((runtime) => ({
        worker_id: runtime.workerId,
        worker_name: runtime.workerName,
        assigned_job_id: runtime.jobId,
        assigned_step_id: stepIdFor(runtime.ordinal, config),
        shift_id: runtime.shiftId,
        state: runtime.state,
        compatibility_score: Number(runtime.compatibility.toFixed(3)),
        speed_factor: Number(runtime.speedFactor.toFixed(3)),
        metrics: {
          current_fatigue_level: round2(runtime.fatigue),
          current_stress_level: round2(runtime.stress),
          effective_throughput_per_hour: round2(runtime.speedFactor * 60),
          effective_error_probability: Number(
            errorProbability(
              runtime,
              (config.job_demands || []).find((item) => item.job_id === runtime.jobId)!
            ).toFixed(4)
          ),
          burnout_hazard_risk: riskFromLevels(runtime.fatigue, runtime.stress),
          throughput_multiplier: Number(runtime.speedFactor.toFixed(3)),
        },
      })),
      warehouses: warehouseStates,
      outputs: buildOutputStates(config),
      recent_errors: [...recentErrors],
    },
  };
}