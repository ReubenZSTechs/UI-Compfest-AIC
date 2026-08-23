// features/simulation_optimisation/api/simulationApi.ts
//
// REVISI (arsitektur Client-Side Simulation):
// Backend TIDAK LAGI punya endpoint "jalankan simulasi" (GET /rl-optimization/
// simulation/live sudah dihapus -- dulu selalu NotImplementedError). Tick
// simulasi di bawah ini (`fetchLiveSimulationState`) memang SUDAH murni lokal
// sejak awal (jitter-based, tanpa network call) -- itu tidak berubah.
//
// Yang berubah: initial state sekarang dibangun dari Digital Twin ASLI lewat
// `fetchDigitalTwin()` (GET /rl-optimization/digital-twin, Fase Inisialisasi),
// bukan dari `FALLBACK_SEED_STATE` hardcoded di bawah. Fallback tetap
// dipertahankan untuk kondisi belum ada factory ter-parse / dev tanpa backend,
// sama seperti pola fallback statis di `features/simulation`.

import { apiClient } from '@/api/client';
import { ENDPOINTS } from '@/api/endpoints';
import type {
  BurnoutRisk,
  CurrentAssignment,
  SimulationResponse,
  StepBreakdown,
  StepStatus,
} from '../types/simulation.types';
import type { DigitalTwin as RlDigitalTwin } from '../types/digitalTwinRl.types';

/** GET /rl-optimization/digital-twin?factory_id=... — Fase Inisialisasi.
 * Backend TIDAK menghitung apa pun di sini, hanya membaca & memetakan data
 * twin yang sudah tersimpan (sumber sama dengan features/digital-twin). */
export async function fetchDigitalTwin(factoryId: string): Promise<RlDigitalTwin | null> {
  try {
    const { data } = await apiClient.get<RlDigitalTwin>(ENDPOINTS.RL_OPTIMIZATION.DIGITAL_TWIN, {
      params: { factory_id: factoryId },
    });
    return data;
  } catch {
    // 404 = belum ada factory ter-parse untuk id ini -- bukan error fatal,
    // caller (useSimulationInit) akan jatuh ke FALLBACK_SEED_STATE.
    return null;
  }
}

const clampFraction = (v: number) => Math.min(1, Math.max(0, v));

function riskFromLevelsInit(fatigue: number, stress: number): BurnoutRisk {
  if (fatigue > 0.65 || stress > 0.55) return 'high';
  if (fatigue > 0.4 || stress > 0.35) return 'medium';
  return 'low';
}

/** Fungsi murni: Digital Twin (struktur asli) -> SimulationResponse (seed tick-0).
 * Ini SATU-SATUNYA tempat initial state dihitung -- tidak ada implementasi
 * kedua di backend, supaya tidak ada risiko divergensi antara keduanya. */
export function buildSeedFromDigitalTwin(twin: RlDigitalTwin): SimulationResponse {
  const assetById = new Map(twin.assets.map((a) => [a.assetId, a]));

  const current_assignments: CurrentAssignment[] = twin.jobDescriptions.map((job) => {
    const asset = assetById.get(job.assignedAssetId);
    // Baseline fatigue/stress diturunkan dari compatibility evaluation kalau
    // ada, atau nilai netral kecil kalau belum dievaluasi -- bukan angka acak.
    const evaluation = twin.llmCompatibilityAndEvaluations.find(
      (ce) => ce.jobId === job.jobId,
    );
    const fatigue = clampFraction(0.15 + (evaluation?.evaluations.errorMultiplier ?? 1) * 0.05);
    const stress = clampFraction(0.12 + job.demands.taskComplexity * 0.2);

    return {
      worker_id: evaluation?.workerId ?? `unassigned-${job.jobId}`,
      assigned_job_id: job.jobId,
      assigned_asset_id: job.assignedAssetId,
      calculated_realtime_metrics: {
        current_fatigue_level: fatigue,
        current_stress_level: stress,
        effective_throughput_per_hour:
          (asset?.baseThroughputCapacity ?? 0) * (evaluation?.evaluations.throughputMultiplier ?? 1),
        effective_error_probability: clampFraction(0.01 * (evaluation?.evaluations.errorMultiplier ?? 1)),
        burnout_hazard_risk: riskFromLevelsInit(fatigue, stress),
      },
    };
  });

  const step_breakdown: StepBreakdown[] = twin.factoryInfo.workflowSequence.map((stepId) => {
    const job = twin.jobDescriptions.find((j) => j.workflowStep === stepId);
    const asset = job ? assetById.get(job.assignedAssetId) : undefined;
    return {
      step_id: stepId,
      step_name: job?.jobTitle ?? stepId,
      status: 'normal' as StepStatus,
      output_generated: asset?.baseThroughputCapacity ?? 0,
      operational_cost_idr: asset?.operationalCostPerHour ?? 0,
    };
  });

  const total_output_units = step_breakdown.length
    ? step_breakdown[step_breakdown.length - 1].output_generated
    : 0;
  const total_operational_cost_idr = step_breakdown.reduce((s, x) => s + x.operational_cost_idr, 0);

  return {
    live_simulation_state: {
      current_assignments,
      system_bottlenecks: [],
      simulation_summary: {
        total_output_units,
        target_output_units: total_output_units || 1,
        production_achievement_percentage: total_output_units ? 100 : 0,
        total_operational_cost_idr,
        cost_per_unit_idr: total_output_units
          ? Number((total_operational_cost_idr / total_output_units).toFixed(2))
          : 0,
        efficiency_score: 75,
      },
      step_breakdown,
      analytical_insight_summary: `Simulasi dimulai dari data twin factory ${twin.factoryInfo.factoryId}.`,
    },
  };
}

// --- Fallback statis (dev tanpa backend / belum ada factory ter-parse) -----
const FALLBACK_SEED_STATE: SimulationResponse = {
  live_simulation_state: {
    current_assignments: [
      { worker_id: 'wrk-01', assigned_job_id: 'job-01', assigned_asset_id: 'ast-01', calculated_realtime_metrics: { current_fatigue_level: 0.2, current_stress_level: 0.18, effective_throughput_per_hour: 300.0, effective_error_probability: 0.01, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-02', assigned_job_id: 'job-02', assigned_asset_id: 'ast-02', calculated_realtime_metrics: { current_fatigue_level: 0.25, current_stress_level: 0.22, effective_throughput_per_hour: 165.0, effective_error_probability: 0.014, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-03', assigned_job_id: 'job-03', assigned_asset_id: 'ast-03', calculated_realtime_metrics: { current_fatigue_level: 0.35, current_stress_level: 0.25, effective_throughput_per_hour: 200.0, effective_error_probability: 0.018, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-04', assigned_job_id: 'job-04', assigned_asset_id: 'ast-04', calculated_realtime_metrics: { current_fatigue_level: 0.3, current_stress_level: 0.2, effective_throughput_per_hour: 216.0, effective_error_probability: 0.015, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-05', assigned_job_id: 'job-05', assigned_asset_id: 'ast-05', calculated_realtime_metrics: { current_fatigue_level: 0.22, current_stress_level: 0.24, effective_throughput_per_hour: 189.0, effective_error_probability: 0.016, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-06', assigned_job_id: 'job-06', assigned_asset_id: 'ast-06', calculated_realtime_metrics: { current_fatigue_level: 0.18, current_stress_level: 0.3, effective_throughput_per_hour: 250.0, effective_error_probability: 0.008, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-07', assigned_job_id: 'job-07', assigned_asset_id: 'ast-07', calculated_realtime_metrics: { current_fatigue_level: 0.72, current_stress_level: 0.58, effective_throughput_per_hour: 253.0, effective_error_probability: 0.03, burnout_hazard_risk: 'high' } },
      { worker_id: 'wrk-08', assigned_job_id: 'job-08', assigned_asset_id: 'ast-08', calculated_realtime_metrics: { current_fatigue_level: 0.12, current_stress_level: 0.15, effective_throughput_per_hour: 209.0, effective_error_probability: 0.012, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-09', assigned_job_id: 'job-09', assigned_asset_id: 'ast-09', calculated_realtime_metrics: { current_fatigue_level: 0.28, current_stress_level: 0.26, effective_throughput_per_hour: 200.0, effective_error_probability: 0.011, burnout_hazard_risk: 'low' } },
      { worker_id: 'wrk-10', assigned_job_id: 'job-10', assigned_asset_id: 'ast-10', calculated_realtime_metrics: { current_fatigue_level: 0.1, current_stress_level: 0.14, effective_throughput_per_hour: 204.0, effective_error_probability: 0.01, burnout_hazard_risk: 'low' } },
    ],
    system_bottlenecks: ['step_07_baking'],
    simulation_summary: {
      total_output_units: 2155.0,
      target_output_units: 2500.0,
      production_achievement_percentage: 86.2,
      total_operational_cost_idr: 14500000.0,
      cost_per_unit_idr: 6728.54,
      efficiency_score: 78.5,
    },
    step_breakdown: [
      { step_id: 'step_01', step_name: 'Preparation', status: 'normal', output_generated: 300.0, operational_cost_idr: 1200000.0 },
      { step_id: 'step_02', step_name: 'Mixing', status: 'normal', output_generated: 280.0, operational_cost_idr: 1300000.0 },
      { step_id: 'step_03', step_name: 'Molding', status: 'normal', output_generated: 270.0, operational_cost_idr: 1150000.0 },
      { step_id: 'step_04', step_name: 'Fermentation', status: 'normal', output_generated: 260.0, operational_cost_idr: 1400000.0 },
      { step_id: 'step_05', step_name: 'Shaping', status: 'normal', output_generated: 250.0, operational_cost_idr: 1250000.0 },
      { step_id: 'step_06', step_name: 'Proofing', status: 'normal', output_generated: 235.0, operational_cost_idr: 1350000.0 },
      { step_id: 'step_07_baking', step_name: 'Baking Process', status: 'bottleneck', output_generated: 200.0, operational_cost_idr: 2500000.0 },
      { step_id: 'step_08', step_name: 'Cooling', status: 'normal', output_generated: 195.0, operational_cost_idr: 1100000.0 },
      { step_id: 'step_09', step_name: 'Sorting', status: 'normal', output_generated: 190.0, operational_cost_idr: 1050000.0 },
      { step_id: 'step_10', step_name: 'Packaging', status: 'normal', output_generated: 185.0, operational_cost_idr: 1100000.0 },
    ],
    analytical_insight_summary:
      "Baking (wrk-07/Bambang) adalah bottleneck utama lini saat ini: fatigue 0.72 dan stress 0.58 mendekati ambang distress (Yerkes-Dodson), dengan burnout_hazard_risk 'high' setelah 5.0 jam kerja dan 5 shift berturut-turut. Rekomendasi: rotasi/istirahat 15 menit untuk wrk-07 dalam waktu dekat.",
  },
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const jitter = (value: number, amount: number, min: number, max: number) =>
  Number(clamp(value + (Math.random() - 0.5) * amount, min, max).toFixed(4));

function riskFromLevels(fatigue: number, stress: number): BurnoutRisk {
  if (fatigue > 0.65 || stress > 0.55) return 'high';
  if (fatigue > 0.4 || stress > 0.35) return 'medium';
  return 'low';
}

function nextAssignment(a: CurrentAssignment): CurrentAssignment {
  const m = a.calculated_realtime_metrics;
  // Workers already flagged high-risk trend upward faster (fatigue compounds);
  // everyone else drifts gently so the flowchart feels alive without being noisy.
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
    },
  };
}

function nextStep(s: StepBreakdown, isBottleneck: boolean): StepBreakdown {
  const cap = isBottleneck ? 30 : 10; // bottleneck output swings more under strain
  return {
    ...s,
    status: isBottleneck ? 'bottleneck' : 'normal',
    output_generated: jitter(s.output_generated, cap, 40, 400),
  };
}

/** Advances the simulation one tick from `previous` (or the seed on the first call)
 * and returns a fresh, internally-consistent snapshot. Simulates network latency. */
export async function fetchLiveSimulationState(
  previous?: SimulationResponse,
): Promise<SimulationResponse> {
  await new Promise((resolve) => setTimeout(resolve, 350 + Math.random() * 250));

  const source = previous ?? FALLBACK_SEED_STATE;
  const bottleneckIds = new Set(source.live_simulation_state.system_bottlenecks);

  const current_assignments = source.live_simulation_state.current_assignments.map(nextAssignment);
  const step_breakdown = source.live_simulation_state.step_breakdown.map((s) =>
    nextStep(s, bottleneckIds.has(s.step_id)),
  );

  const total_output_units = Number(
    step_breakdown[step_breakdown.length - 1].output_generated.toFixed(1),
  );
  const total_operational_cost_idr = step_breakdown.reduce(
    (sum, s) => sum + s.operational_cost_idr,
    0,
  );
  const { target_output_units } = source.live_simulation_state.simulation_summary;

  return {
    live_simulation_state: {
      current_assignments,
      system_bottlenecks: source.live_simulation_state.system_bottlenecks,
      step_breakdown,
      simulation_summary: {
        total_output_units,
        target_output_units,
        production_achievement_percentage: Number(
          ((total_output_units / target_output_units) * 100).toFixed(1),
        ),
        total_operational_cost_idr,
        cost_per_unit_idr: Number((total_operational_cost_idr / total_output_units).toFixed(2)),
        efficiency_score: jitter(
          source.live_simulation_state.simulation_summary.efficiency_score,
          3,
          40,
          98,
        ),
      },
      analytical_insight_summary: source.live_simulation_state.analytical_insight_summary,
    },
  };
}

export function getSeedSimulationState(): SimulationResponse {
  return FALLBACK_SEED_STATE;
}