// frontend/src/features/simulation/api/simulationApi.ts

// Real API — fetch config sekali dari backend, lalu jalankan tick loop lokal.
// Tick logic di file ini SENGAJA identik dengan `simulationApi.mock.ts` kamu;
// bedanya cuma satu: semua tabel/kapasitas/worker seed sekarang datang dari
// GET /api/v1/simulation/config, bukan hardcoded di file ini.

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
import { WAREHOUSE_STEP_ID as FALLBACK_WAREHOUSE_STEP_ID } from '../types/simulation.types';
import { API_BASE_URL } from '../../../config/env';

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const jitter = (value: number, amount: number, min: number, max: number) =>
  Number(clamp(value + (Math.random() - 0.5) * amount, min, max).toFixed(4));
const round2 = (value: number) => Number(value.toFixed(2));

// ---------------------------------------------------------------------------
// Config types — bentuk response dari GET /api/v1/simulation/config
// ---------------------------------------------------------------------------

interface MaterialTemplate {
  name: string;
  unit: string;
}

interface SeedAssignment {
  worker_id: string;
  assigned_job_id: string;
  assigned_asset_id: string;
  calculated_realtime_metrics: RealtimeMetrics;
}

interface SimulationConfig {
  materials_by_ordinal: Record<number, MaterialTemplate>;
  step_names: Record<number, string>;
  step_cost_base: Record<number, number>;
  capacity_by_ordinal: Record<number, number>;
  batch_in_by_ordinal: Record<number, number>;
  batch_out_by_ordinal: Record<number, number>;
  cycle_ticks_by_ordinal: Record<number, number>;
  bottleneck_fill_threshold: number;
  idle_qty_threshold: number;
  station_1_safety_margin: number;
  warehouse_capacity: number;
  warehouse_feed_rate: number;
  warehouse_step_id: string;
  worker_throughput_multiplier: Record<string, number>;
  seed_assignments: SeedAssignment[];
  shift_start_minutes: number;
  break_start_elapsed: number;
  break_end_elapsed: number;
  shift_end_elapsed: number;
  analytical_insight_summary: string;
  target_output_units: number;
  initial_batch_seq: number;
}

const CONFIG_ENDPOINT = `${API_BASE_URL}/simulation/config`;

let configPromise: Promise<SimulationConfig> | null = null;

async function loadConfig(): Promise<SimulationConfig> {
  if (!configPromise) {
    configPromise = fetch(CONFIG_ENDPOINT)
      .then((res) => {
        if (!res.ok) throw new Error(`Gagal memuat konfigurasi simulasi (${res.status})`);
        return res.json() as Promise<SimulationConfig>;
      })
      .catch((err) => {
        // Reset supaya percobaan berikutnya bisa retry fetch, bukan stuck di promise gagal
        configPromise = null;
        throw err;
      });
  }
  return configPromise;
}

// Di-export supaya konsumer lain (mis. simulationStore.ts saat reset()) bisa
// ambil config yang sama tanpa perlu tick loop jalan dulu. Karena
// `configPromise` di-cache di module scope, pemanggilan ini setelah initial
// load biasanya instan -- tidak fetch ulang ke backend.
export async function getSimulationConfig(): Promise<SimulationConfig> {
  return loadConfig();
}

// ---------------------------------------------------------------------------
// Engine state (module-scoped persistence) — sama seperti versi mock
// ---------------------------------------------------------------------------

interface BatchState {
  ticksRemaining: number;
  inProgressBatchCode: string | null;
  inProgressQty: number;
  readyToShip: { qty: number; batchCode: string } | null;
}

let batchSeq = 0;
let finishedGoodsTotal = 0;
let warehouse: WarehouseState = { capacity: 0, current_stock: 0 };
let currentTickMinutes = 0;
const materialByOrdinal: Record<number, MaterialInProcess> = {};
const batchStateByOrdinal: Record<number, BatchState> = {};
const totalOutputByOrdinal: Record<number, number> = {};

// `warehouse` di atas cuma placeholder {0,0} sebelum config berhasil
// di-fetch (config datang async dari backend, beda dengan versi mock yang
// dulu punya WAREHOUSE_CAPACITY sebagai konstanta sinkron). Tanpa ini,
// warehouse akan tampil "0 / 0 kg" terus sampai user klik Reset, karena
// resetMockSimulationState() cuma dipanggil dari tombol Reset, bukan
// otomatis saat initial load.
let engineInitialized = false;

function ensureEngineInitialized(config: SimulationConfig) {
  if (engineInitialized) return;
  engineInitialized = true;
  batchSeq = config.initial_batch_seq;
  warehouse = { capacity: config.warehouse_capacity, current_stock: config.warehouse_capacity };
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
  warehouse = { capacity: config.warehouse_capacity, current_stock: config.warehouse_capacity };
  Object.keys(materialByOrdinal).forEach((k) => delete materialByOrdinal[Number(k)]);
  Object.keys(batchStateByOrdinal).forEach((k) => delete batchStateByOrdinal[Number(k)]);
  Object.keys(totalOutputByOrdinal).forEach((k) => delete totalOutputByOrdinal[Number(k)]);
}

function riskFromLevels(fatigue: number, stress: number): BurnoutRisk {
  if (fatigue > 0.65 || stress > 0.55) return 'high';
  if (fatigue > 0.4 || stress > 0.35) return 'medium';
  return 'low';
}

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
  };
}

function statusFor(waitingQty: number, inProcessQty: number, capacity: number, ordinal: number, config: SimulationConfig): 'idle' | 'bottleneck' | 'normal' {
  const totalWip = waitingQty + inProcessQty;
  if (totalWip <= config.idle_qty_threshold) return 'idle';
  if (ordinal === 1) return 'normal';
  if (totalWip / capacity >= config.bottleneck_fill_threshold) return 'bottleneck';
  return 'normal';
}

function nextAssignment(a: CurrentAssignment, isBreak: boolean, isStationIdle: boolean): CurrentAssignment {
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

function buildStepBreakdown(speedByOrdinal: Record<number, number>, config: SimulationConfig): StepBreakdown[] {
  return Array.from({ length: 10 }, (_, i) => {
    const ordinal = i + 1;
    const stepId = stepIdFor(ordinal);
    const material = materialByOrdinal[ordinal];
    const batchState = batchStateByOrdinal[ordinal];

    const waitingQty = material.quantity;
    const inProcessQty = batchState?.inProgressQty ?? 0;
    const totalWip = waitingQty + inProcessQty;

    const speed = speedByOrdinal[ordinal] ?? 1;
    const status = statusFor(waitingQty, inProcessQty, material.capacity, ordinal, config);

    const nominalRatePerHour = Number(
      ((config.batch_out_by_ordinal[ordinal] / config.cycle_ticks_by_ordinal[ordinal]) * speed * 12).toFixed(1)
    );

    return {
      step_id: stepId,
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
    };
  });
}

let seedAssignmentsCache: CurrentAssignment[] | null = null;
let efficiencyScore = 78.5;

function buildSeedAssignments(config: SimulationConfig): CurrentAssignment[] {
  if (!seedAssignmentsCache) {
    seedAssignmentsCache = config.seed_assignments.map((s) => ({
      worker_id: s.worker_id,
      assigned_job_id: s.assigned_job_id,
      assigned_asset_id: s.assigned_asset_id,
      calculated_realtime_metrics: { ...s.calculated_realtime_metrics },
    }));
  }
  return seedAssignmentsCache;
}

export async function getSeedSimulationState(): Promise<SimulationResponse> {
  const config = await loadConfig();
  ensureEngineInitialized(config);
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) ensureInitialized(ordinal, config);

  const assignments = buildSeedAssignments(config);
  const speedByOrdinal = calculateSpeedByOrdinal(assignments);
  const step_breakdown = buildStepBreakdown(speedByOrdinal, config);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);

  return {
    live_simulation_state: {
      current_assignments: assignments,
      system_bottlenecks,
      warehouse: { ...warehouse },
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
    },
  };
}

export async function fetchLiveSimulationState(previous?: SimulationResponse): Promise<SimulationResponse> {
  const config = await loadConfig();
  ensureEngineInitialized(config);
  await new Promise((resolve) => setTimeout(resolve, 300 + Math.random() * 200));

  const source = previous ?? (await getSeedSimulationState());
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) ensureInitialized(ordinal, config);

  if (previous) currentTickMinutes += 1;
  const shiftInfo = calculateShiftInfo(currentTickMinutes, config);

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
      const destSpare = config.capacity_by_ordinal[destOrdinal] - dest.quantity;

      if (pending.qty <= destSpare + 1e-9) {
        dest.quantity = round2(dest.quantity + pending.qty);
        dest.batch_code = pending.batchCode;
        activeTransfers.push({
          from_step_id: stepIdFor(ordinal),
          to_step_id: stepIdFor(destOrdinal),
          batch_code: pending.batchCode,
          quantity: pending.qty,
          unit: config.materials_by_ordinal[destOrdinal].unit,
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
        const outputQty = config.batch_out_by_ordinal[ordinal];

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
      const batchIn = config.batch_in_by_ordinal[ordinal];
      if (material.quantity + 1e-9 < batchIn) continue;

      material.quantity = round2(material.quantity - batchIn);
      batchState.ticksRemaining = effectiveCycleTicks(ordinal, speedByOrdinal[ordinal] ?? 1, config);
      batchState.inProgressBatchCode = nextBatchCode();
      batchState.inProgressQty = batchIn;
    }

    // 4) WAREHOUSE -> STATION 1 feed
    const station1 = materialByOrdinal[1];
    const station1SafeCeiling = (config.bottleneck_fill_threshold - config.station_1_safety_margin) * config.capacity_by_ordinal[1];
    const station1SafeSpare = Math.max(0, station1SafeCeiling - station1.quantity);
    const warehouseFeed = Math.max(0, Math.min(config.warehouse_feed_rate, warehouse.current_stock, station1SafeSpare));

    if (warehouseFeed > 0.05) {
      warehouse = { capacity: warehouse.capacity, current_stock: round2(warehouse.current_stock - warehouseFeed) };
      station1.quantity = round2(station1.quantity + warehouseFeed);
      activeTransfers.push({
        from_step_id: config.warehouse_step_id ?? FALLBACK_WAREHOUSE_STEP_ID,
        to_step_id: stepIdFor(1),
        batch_code: station1.batch_code,
        quantity: round2(warehouseFeed),
        unit: config.materials_by_ordinal[1].unit,
      });
    }
  }

  const isStationIdleMap: Record<number, boolean> = {};
  for (let ordinal = 1; ordinal <= 10; ordinal += 1) {
    const batchState = batchStateByOrdinal[ordinal];
    const material = materialByOrdinal[ordinal];
    const batchIn = config.batch_in_by_ordinal[ordinal];
    isStationIdleMap[ordinal] = batchState.ticksRemaining === 0 && material.quantity + 1e-9 < batchIn;
  }

  const current_assignments = source.live_simulation_state.current_assignments.map((a) => {
    const ordinal = getOrdinalFromAssignment(a);
    const isStationIdle = isStationIdleMap[ordinal] ?? false;
    return nextAssignment(a, shiftInfo.is_break_time, isStationIdle);
  });

  const updatedSpeedByOrdinal = calculateSpeedByOrdinal(current_assignments);
  const step_breakdown = buildStepBreakdown(updatedSpeedByOrdinal, config);
  const system_bottlenecks = step_breakdown.filter((s) => s.status === 'bottleneck').map((s) => s.step_id);
  const total_operational_cost_idr = step_breakdown.reduce((sum, s) => sum + s.operational_cost_idr, 0);
  const roundedOutput = round2(finishedGoodsTotal);
  const targetOutput = source.live_simulation_state.simulation_summary.target_output_units;

  efficiencyScore = jitter(source.live_simulation_state.simulation_summary.efficiency_score, 3, 40, 98);

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
        efficiency_score: efficiencyScore,
      },
      analytical_insight_summary: source.live_simulation_state.analytical_insight_summary,
      shift_info: shiftInfo,
    },
  };
}