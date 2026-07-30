// Stand-in for a real `simulationApi.ts` (REST) or `websocket.ts` (live push) source.

import type {
  ActiveTransfer,
  BurnoutRisk,
  CurrentAssignment,
  MaterialInProcess,
  OperationalStatus,
  RealtimeMetrics,
  ShiftScheduleInfo,
  SimulationResponse,
  StepBreakdown,
  WarehouseState,
} from '../types/simulation.types';
import { WAREHOUSE_STEP_ID } from '../types/simulation.types';

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const jitter = (value: number, amount: number, min: number, max: number) =>
  Number(clamp(value + (Math.random() - 0.5) * amount, min, max).toFixed(4));
const round2 = (value: number) => Number(value.toFixed(2));

// ---------------------------------------------------------------------------
// Per-station templates & Capacity Config
// ---------------------------------------------------------------------------

interface MaterialTemplate {
  name: string;
  unit: string;
}

const MATERIAL_BY_ORDINAL: Record<number, MaterialTemplate> = {
  1: { name: 'Bahan Baku Tertimbang', unit: 'kg' },
  2: { name: 'Adonan Tercampur', unit: 'kg' },
  3: { name: 'Potongan Adonan', unit: 'pcs' },
  4: { name: 'Adonan Terbentuk', unit: 'pcs' },
  5: { name: 'Loyang Terisi', unit: 'loyang' },
  6: { name: 'Loyang Proofing', unit: 'loyang' },
  7: { name: 'Loyang Panggang', unit: 'loyang' },
  8: { name: 'Produk Mendingin', unit: 'pcs' },
  9: { name: 'Produk Lolos Sortir', unit: 'pcs' },
  10: { name: 'Produk Terkemas', unit: 'pack' },
};

const STEP_NAMES: Record<number, string> = {
  1: 'Preparation', 2: 'Mixing', 3: 'Molding', 4: 'Fermentation', 5: 'Shaping',
  6: 'Proofing', 7: 'Baking Process', 8: 'Cooling', 9: 'Sorting', 10: 'Packaging',
};

const STEP_COST_BASE: Record<number, number> = {
  1: 1200000, 2: 1300000, 3: 1150000, 4: 1400000, 5: 1250000,
  6: 1350000, 7: 2500000, 8: 1100000, 9: 1050000, 10: 1100000,
};

const CAPACITY_BY_ORDINAL: Record<number, number> = {
  1: 40, 2: 46, 3: 420, 4: 270, 5: 48, 6: 24, 7: 28, 8: 320, 9: 260, 10: 42,
};

// ---------------------------------------------------------------------------
// RECIPE TABLE — single source of truth for mass balance.
// ---------------------------------------------------------------------------

const BATCH_IN_BY_ORDINAL: Record<number, number> = {
  1: 20, 2: 18, 3: 130, 4: 132, 5: 18, 6: 9, 7: 14, 8: 120, 9: 110, 10: 21,
};

const BATCH_OUT_BY_ORDINAL: Record<number, number> = {
  1: 19.6, 2: 252, 3: 126, 4: 11, 5: 18, 6: 9, 7: 168, 8: 114, 9: 11, 10: 21,
};

const CYCLE_TICKS_BY_ORDINAL: Record<number, number> = {
  1: 2, 2: 2, 3: 1, 4: 1, 5: 3, 6: 4, 7: 5, 8: 1, 9: 1, 10: 2,
};

const BOTTLENECK_FILL_THRESHOLD = 0.7;
const IDLE_QTY_THRESHOLD = 0.05;
const STATION_1_SAFETY_MARGIN = 0.03;

const WAREHOUSE_CAPACITY = 4000;
const WAREHOUSE_FEED_RATE = 9;

const WORKER_THROUGHPUT_MULTIPLIER: Record<string, number> = {
  'wrk-01': 1.05, 'wrk-02': 1.1,  'wrk-03': 1.0,  'wrk-04': 1.08, 'wrk-05': 1.05,
  'wrk-06': 1.0,  'wrk-11': 1.04, // Proofing team (2 workers)
  'wrk-07': 1.15, 'wrk-12': 1.10, // Baking team (2 workers)
  'wrk-08': 0.95, 'wrk-09': 1.0,  'wrk-10': 1.02,
};

function stepIdFor(ordinal: number): string {
  return ordinal === 7 ? 'step_07_baking' : `step_${String(ordinal).padStart(2, '0')}`;
}

function getOrdinalFromAssignment(assignment: CurrentAssignment): number {
  const match = assignment.assigned_job_id.match(/job-(\d+)/);
  if (match) return parseInt(match[1], 10);
  const assetMatch = assignment.assigned_asset_id.match(/ast-(\d+)/);
  if (assetMatch) return parseInt(assetMatch[1], 10);
  return 1;
}

function effectiveSpeedFactor(metrics: RealtimeMetrics): number {
  const fatiguePenalty = metrics.current_fatigue_level * 0.35;
  const stressPenalty = metrics.current_stress_level * 0.15;
  return clamp(metrics.throughput_multiplier - fatiguePenalty - stressPenalty, 0.2, 1.6);
}

/**
 * MULTI-WORKER SPEED LOGIC:
 * Menjumlahkan kecepatan seluruh worker di pos tersebut (kumulatif).
 */
function calculateSpeedByOrdinal(assignments: CurrentAssignment[]): Record<number, number> {
  const speedSums: Record<number, number> = {};

  assignments.forEach((a) => {
    const ordinal = getOrdinalFromAssignment(a);
    const speed = effectiveSpeedFactor(a.calculated_realtime_metrics);
    speedSums[ordinal] = (speedSums[ordinal] || 0) + speed;
  });

  const speedByOrdinal: Record<number, number> = {};
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
    speedByOrdinal[ordinal] = speedSums[ordinal] ?? 1.0;
  }
  return speedByOrdinal;
}

function effectiveCycleTicks(ordinal: number, speed: number): number {
  return Math.max(1, Math.round(CYCLE_TICKS_BY_ORDINAL[ordinal] / speed));
}

// ---------------------------------------------------------------------------
// SHIFT & TIME SCHEDULER
// ---------------------------------------------------------------------------

const SHIFT_START_MINUTES = 8 * 60; // 08:00 (480 mins)
const BREAK_START_ELAPSED = 4 * 60; // 12:00 (240 mins elapsed)
const BREAK_END_ELAPSED = 5 * 60;   // 13:00 (300 mins elapsed)
const SHIFT_END_ELAPSED = 9 * 60;   // 17:00 (540 mins elapsed)

let currentTickMinutes = 0;

function calculateShiftInfo(elapsedMinutes: number): ShiftScheduleInfo {
  const currentTotalMins = SHIFT_START_MINUTES + elapsedMinutes;
  const hours = Math.floor(currentTotalMins / 60) % 24;
  const mins = currentTotalMins % 60;
  const timeFormatted = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;

  const isBreak = elapsedMinutes >= BREAK_START_ELAPSED && elapsedMinutes < BREAK_END_ELAPSED;
  const isShiftEnded = elapsedMinutes >= SHIFT_END_ELAPSED;

  let operationalStatus: OperationalStatus = 'working';
  if (isShiftEnded) {
    operationalStatus = 'shift_ended';
  } else if (isBreak) {
    operationalStatus = 'break';
  }

  return {
    current_time_formatted: timeFormatted,
    current_tick_minutes: elapsedMinutes,
    shift_start_time: '08:00',
    shift_end_time: '17:00',
    break_start_time: '12:00',
    break_end_time: '13:00',
    operational_status: operationalStatus,
    is_break_time: isBreak,
    is_shift_ended: isShiftEnded,
  };
}

// ---------------------------------------------------------------------------
// Engine state (module-scoped persistence)
// ---------------------------------------------------------------------------

interface BatchState {
  ticksRemaining: number;
  inProgressBatchCode: string | null;
  inProgressQty: number; // Jumlah material yang sedang aktif diproses
  readyToShip: { qty: number; batchCode: string } | null;
}

let batchSeq = 232;
let finishedGoodsTotal = 0;
let warehouse: WarehouseState = { capacity: WAREHOUSE_CAPACITY, current_stock: WAREHOUSE_CAPACITY };
const materialByOrdinal: Record<number, MaterialInProcess> = {};
const batchStateByOrdinal: Record<number, BatchState> = {};
const totalOutputByOrdinal: Record<number, number> = {};

function nextBatchCode(): string {
  batchSeq += 1;
  return `#B-${batchSeq}`;
}

function ensureInitialized(ordinal: number) {
  if (!materialByOrdinal[ordinal]) {
    const template = MATERIAL_BY_ORDINAL[ordinal];
    materialByOrdinal[ordinal] = {
      batch_code: nextBatchCode(),
      material_name: template.name,
      quantity: 0,
      in_process_quantity: 0,
      capacity: CAPACITY_BY_ORDINAL[ordinal],
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

export function resetMockSimulationState() {
  batchSeq = 232;
  finishedGoodsTotal = 0;
  currentTickMinutes = 0;
  warehouse = { capacity: WAREHOUSE_CAPACITY, current_stock: WAREHOUSE_CAPACITY };
  Object.keys(materialByOrdinal).forEach((k) => delete materialByOrdinal[Number(k)]);
  Object.keys(batchStateByOrdinal).forEach((k) => delete batchStateByOrdinal[Number(k)]);
  Object.keys(totalOutputByOrdinal).forEach((k) => delete totalOutputByOrdinal[Number(k)]);
}

function riskFromLevels(fatigue: number, stress: number): BurnoutRisk {
  if (fatigue > 0.65 || stress > 0.55) return 'high';
  if (fatigue > 0.4 || stress > 0.35) return 'medium';
  return 'low';
}

function nextAssignment(
  a: CurrentAssignment,
  isBreak: boolean,
  isStationIdle: boolean
): CurrentAssignment {
  const m = a.calculated_realtime_metrics;
  
  if (isBreak || isStationIdle) {
    const fatigue = clamp(m.current_fatigue_level - 0.02, 0.05, 0.98);
    const stress = clamp(m.current_stress_level - 0.015, 0.05, 0.95);
    return {
      ...a,
      calculated_realtime_metrics: {
        ...m,
        current_fatigue_level: round2(fatigue),
        current_stress_level: round2(stress),
        burnout_hazard_risk: riskFromLevels(fatigue, stress),
      },
    };
  }

  const drift = m.burnout_hazard_risk === 'high' ? 0.045 : 0.02;
  const fatigue = jitter(m.current_fatigue_level + drift * 0.15, 0.05, 0.05, 0.98);
  const stress = jitter(m.current_stress_level + drift * 0.1, 0.05, 0.05, 0.95);
  return {
    ...a,
    calculated_realtime_metrics: {
      current_fatigue_level: fatigue,
      current_stress_level: stress,
      effective_throughput_per_hour: jitter(m.effective_throughput_per_hour, 10, 50, 400),
      effective_error_probability: jitter(m.effective_error_probability, 0.006, 0.002, 0.25),
      burnout_hazard_risk: riskFromLevels(fatigue, stress),
      throughput_multiplier: m.throughput_multiplier,
    },
  };
}

function statusFor(
  waitingQty: number,
  inProcessQty: number,
  capacity: number,
  ordinal: number
): 'idle' | 'bottleneck' | 'normal' {
  const totalWip = waitingQty + inProcessQty;
  if (totalWip <= IDLE_QTY_THRESHOLD) return 'idle';
  if (ordinal === 1) return 'normal';
  if (totalWip / capacity >= BOTTLENECK_FILL_THRESHOLD) return 'bottleneck';
  return 'normal';
}

// ---------------------------------------------------------------------------
// Seed Data (12 Workers)
// ---------------------------------------------------------------------------

function seedMetrics(base: Omit<RealtimeMetrics, 'throughput_multiplier'>, workerId: string): RealtimeMetrics {
  return { ...base, throughput_multiplier: WORKER_THROUGHPUT_MULTIPLIER[workerId] ?? 1.0 };
}

const SEED_ASSIGNMENTS: CurrentAssignment[] = [
  { worker_id: 'wrk-01', assigned_job_id: 'job-01', assigned_asset_id: 'ast-01', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.2, current_stress_level: 0.18, effective_throughput_per_hour: 300.0, effective_error_probability: 0.01, burnout_hazard_risk: 'low' }, 'wrk-01') },
  { worker_id: 'wrk-02', assigned_job_id: 'job-02', assigned_asset_id: 'ast-02', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.25, current_stress_level: 0.22, effective_throughput_per_hour: 165.0, effective_error_probability: 0.014, burnout_hazard_risk: 'low' }, 'wrk-02') },
  { worker_id: 'wrk-03', assigned_job_id: 'job-03', assigned_asset_id: 'ast-03', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.35, current_stress_level: 0.25, effective_throughput_per_hour: 200.0, effective_error_probability: 0.018, burnout_hazard_risk: 'low' }, 'wrk-03') },
  { worker_id: 'wrk-04', assigned_job_id: 'job-04', assigned_asset_id: 'ast-04', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.3, current_stress_level: 0.2, effective_throughput_per_hour: 216.0, effective_error_probability: 0.015, burnout_hazard_risk: 'low' }, 'wrk-04') },
  { worker_id: 'wrk-05', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' }, 'wrk-05') },
  { worker_id: 'wrk-13', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' }, 'wrk-05') },
  { worker_id: 'wrk-14', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' }, 'wrk-05') },
  { worker_id: 'wrk-15', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' }, 'wrk-05') },
  { worker_id: 'wrk-16', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' }, 'wrk-05') },
  { worker_id: 'wrk-06', assigned_job_id: 'job-06', assigned_asset_id: 'ast-06', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.18, current_stress_level: 0.3, effective_throughput_per_hour: 250.0, effective_error_probability: 0.008, burnout_hazard_risk: 'low' }, 'wrk-06') },
  { worker_id: 'wrk-11', assigned_job_id: 'job-06', assigned_asset_id: 'ast-06', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.20, current_stress_level: 0.22, effective_throughput_per_hour: 240.0, effective_error_probability: 0.01, burnout_hazard_risk: 'low' }, 'wrk-11') },
  { worker_id: 'wrk-07', assigned_job_id: 'job-07', assigned_asset_id: 'ast-07', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.72, current_stress_level: 0.58, effective_throughput_per_hour: 253.0, effective_error_probability: 0.03, burnout_hazard_risk: 'high' }, 'wrk-07') },
  { worker_id: 'wrk-12', assigned_job_id: 'job-07', assigned_asset_id: 'ast-07', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.15, current_stress_level: 0.18, effective_throughput_per_hour: 260.0, effective_error_probability: 0.009, burnout_hazard_risk: 'low' }, 'wrk-12') },
  { worker_id: 'wrk-08', assigned_job_id: 'job-08', assigned_asset_id: 'ast-08', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.12, current_stress_level: 0.15, effective_throughput_per_hour: 209.0, effective_error_probability: 0.012, burnout_hazard_risk: 'low' }, 'wrk-08') },
  { worker_id: 'wrk-09', assigned_job_id: 'job-09', assigned_asset_id: 'ast-09', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.28, current_stress_level: 0.26, effective_throughput_per_hour: 200.0, effective_error_probability: 0.011, burnout_hazard_risk: 'low' }, 'wrk-09') },
  { worker_id: 'wrk-10', assigned_job_id: 'job-10', assigned_asset_id: 'ast-10', calculated_realtime_metrics: seedMetrics({ current_fatigue_level: 0.1, current_stress_level: 0.14, effective_throughput_per_hour: 204.0, effective_error_probability: 0.01, burnout_hazard_risk: 'low' }, 'wrk-10') },
];

const INSIGHT =
  'Simulasi dinamis aktif. Pos dengan multi-worker memiliki kapasitas pemrosesan lebih tinggi dan menghabiskan material lebih cepat. Saat material di pos kosong, pekerja akan otomatis beristirahat dan memulihkan fatigue/stress.';

function buildStepBreakdown(speedByOrdinal: Record<number, number>): StepBreakdown[] {
  return Array.from({ length: 10 }, (_, i) => {
    const ordinal = i + 1;
    const stepId = stepIdFor(ordinal);
    const material = materialByOrdinal[ordinal];
    const batchState = batchStateByOrdinal[ordinal];

    const waitingQty = material.quantity;
    const inProcessQty = batchState?.inProgressQty ?? 0;
    const totalWip = waitingQty + inProcessQty;

    const speed = speedByOrdinal[ordinal] ?? 1;
    const status = statusFor(waitingQty, inProcessQty, material.capacity, ordinal);

    // Kecepatan produksi yang dikalkulasi ke estimasi rate per jam
    const nominalRatePerHour = Number(
      ((BATCH_OUT_BY_ORDINAL[ordinal] / CYCLE_TICKS_BY_ORDINAL[ordinal]) * speed * 12).toFixed(1)
    );

    return {
      step_id: stepId,
      step_name: STEP_NAMES[ordinal],
      status,
      // Output per jam (tersedia melalui output_generated dan output_per_hour)
      output_generated: nominalRatePerHour,
      output_per_hour: nominalRatePerHour,
      // Akumulasi total output yang diproduksi pos ini sejak simulasi dimulai
      total_output_produced: round2(totalOutputByOrdinal[ordinal] ?? 0),
      operational_cost_idr: STEP_COST_BASE[ordinal],
      current_material: {
        ...material,
        quantity: waitingQty,
        in_process_quantity: inProcessQty,
      },
      speed_multiplier: Number(speed.toFixed(2)),
      wip_fill_pct: Number(((totalWip / material.capacity) * 100).toFixed(1)),
    };
  });
}

export function getSeedSimulationState(): SimulationResponse {
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) ensureInitialized(ordinal);
  const speedByOrdinal = calculateSpeedByOrdinal(SEED_ASSIGNMENTS);

  const step_breakdown = buildStepBreakdown(speedByOrdinal);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);

  return {
    live_simulation_state: {
      current_assignments: SEED_ASSIGNMENTS,
      system_bottlenecks,
      warehouse: { ...warehouse },
      simulation_summary: {
        total_output_units: finishedGoodsTotal,
        target_output_units: 2500.0,
        production_achievement_percentage: Number(((finishedGoodsTotal / 2500) * 100).toFixed(1)),
        total_operational_cost_idr,
        cost_per_unit_idr: 0,
        efficiency_score: 78.5,
      },
      step_breakdown,
      active_transfers: [],
      analytical_insight_summary: INSIGHT,
      shift_info: calculateShiftInfo(currentTickMinutes),
    },
  };
}

// ---------------------------------------------------------------------------
// Tick advance
// ---------------------------------------------------------------------------

export async function fetchLiveSimulationState(
  previous?: SimulationResponse,
): Promise<SimulationResponse> {
  await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 200));

  const source = previous ?? getSeedSimulationState();
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) ensureInitialized(ordinal);

  if (previous) {
    currentTickMinutes += 1;
  }
  const shiftInfo = calculateShiftInfo(currentTickMinutes);

  const speedByOrdinal = calculateSpeedByOrdinal(source.live_simulation_state.current_assignments);
  const activeTransfers: ActiveTransfer[] = [];

  if (!shiftInfo.is_break_time && !shiftInfo.is_shift_ended) {
    // 1) SHIP PHASE
    for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
      const batchState = batchStateByOrdinal[ordinal];
      const pending = batchState.readyToShip;
      if (!pending) continue;

      if (ordinal === 10) {
        finishedGoodsTotal = round2(finishedGoodsTotal + pending.qty);
        batchState.readyToShip = null;
        continue;
      }

      const destOrdinal = ordinal + 1;
      const dest = materialByOrdinal[destOrdinal];
      const destSpare = CAPACITY_BY_ORDINAL[destOrdinal] - dest.quantity;

      if (pending.qty <= destSpare + 1e-9) {
        dest.quantity = round2(dest.quantity + pending.qty);
        dest.batch_code = pending.batchCode;
        activeTransfers.push({
          from_step_id: stepIdFor(ordinal),
          to_step_id: stepIdFor(destOrdinal),
          batch_code: pending.batchCode,
          quantity: pending.qty,
          unit: MATERIAL_BY_ORDINAL[destOrdinal].unit,
        });
        batchState.readyToShip = null;
      }
    }

    // 2) CYCLE-COMPLETION PHASE
    for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
      const batchState = batchStateByOrdinal[ordinal];
      if (batchState.ticksRemaining <= 0) continue;

      batchState.ticksRemaining -= 1;
      if (batchState.ticksRemaining === 0) {
        const outputQty = BATCH_OUT_BY_ORDINAL[ordinal];

        batchState.readyToShip = {
          qty: outputQty,
          batchCode: batchState.inProgressBatchCode ?? nextBatchCode(),
        };

        totalOutputByOrdinal[ordinal] = round2((totalOutputByOrdinal[ordinal] ?? 0) + outputQty);

        batchState.inProgressBatchCode = null;
        batchState.inProgressQty = 0;
      }
    }

    // 3) START PHASE
    for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
      const batchState = batchStateByOrdinal[ordinal];
      if (batchState.ticksRemaining > 0 || batchState.readyToShip) continue;

      const material = materialByOrdinal[ordinal];
      const batchIn = BATCH_IN_BY_ORDINAL[ordinal];
      if (material.quantity + 1e-9 < batchIn) continue;

      material.quantity = round2(material.quantity - batchIn);
      batchState.ticksRemaining = effectiveCycleTicks(ordinal, speedByOrdinal[ordinal] ?? 1);
      batchState.inProgressBatchCode = nextBatchCode();
      batchState.inProgressQty = batchIn;
    }

    // 4) WAREHOUSE -> STATION 1 feed
    const station1 = materialByOrdinal[1];
    const station1SafeCeiling = (BOTTLENECK_FILL_THRESHOLD - STATION_1_SAFETY_MARGIN) * CAPACITY_BY_ORDINAL[1];
    const station1SafeSpare = Math.max(0, station1SafeCeiling - station1.quantity);
    const warehouseFeed = Math.max(0, Math.min(WAREHOUSE_FEED_RATE, warehouse.current_stock, station1SafeSpare));

    if (warehouseFeed > 0.05) {
      warehouse = { capacity: warehouse.capacity, current_stock: round2(warehouse.current_stock - warehouseFeed) };
      station1.quantity = round2(station1.quantity + warehouseFeed);
      activeTransfers.push({
        from_step_id: WAREHOUSE_STEP_ID,
        to_step_id: stepIdFor(1),
        batch_code: station1.batch_code,
        quantity: round2(warehouseFeed),
        unit: MATERIAL_BY_ORDINAL[1].unit,
      });
    }
  }

  const isStationIdleMap: Record<number, boolean> = {};
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
    const batchState = batchStateByOrdinal[ordinal];
    const material = materialByOrdinal[ordinal];
    const batchIn = BATCH_IN_BY_ORDINAL[ordinal];

    const isIdle = batchState.ticksRemaining === 0 && material.quantity + 1e-9 < batchIn;
    isStationIdleMap[ordinal] = isIdle;
  }

  const current_assignments = source.live_simulation_state.current_assignments.map((a) => {
    const ordinal = getOrdinalFromAssignment(a);
    const isStationIdle = isStationIdleMap[ordinal] ?? false;
    return nextAssignment(a, shiftInfo.is_break_time, isStationIdle);
  });

  const updatedSpeedByOrdinal = calculateSpeedByOrdinal(current_assignments);

  const step_breakdown = buildStepBreakdown(updatedSpeedByOrdinal);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);
  const roundedOutput = round2(finishedGoodsTotal);
  const targetOutput = source.live_simulation_state.simulation_summary.target_output_units;

  return {
    live_simulation_state: {
      current_assignments,
      system_bottlenecks,
      warehouse: { ...warehouse },
      step_breakdown,
      active_transfers: activeTransfers,
      simulation_summary: {
        total_output_units: roundedOutput,
        target_output_units: targetOutput,
        production_achievement_percentage: Number(((roundedOutput / targetOutput) * 100).toFixed(1)),
        total_operational_cost_idr,
        cost_per_unit_idr: roundedOutput > 0 ? Number((total_operational_cost_idr / roundedOutput).toFixed(2)) : 0,
        efficiency_score: jitter(source.live_simulation_state.simulation_summary.efficiency_score, 3, 40, 98),
      },
      analytical_insight_summary: source.live_simulation_state.analytical_insight_summary,
      shift_info: shiftInfo,
    },
  };
}