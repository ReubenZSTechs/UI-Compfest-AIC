// features/simulation/hooks/useSimulationRunner.ts

import { useEffect, useRef } from 'react';
import { fetchLiveSimulationState } from '../api/simulationApi';
import { useSimulationStore } from '../store/simulationStore';
import type { SimulationResponse, ActiveTransfer } from '../types/simulation.types';

// Kecepatan normal (1x) = 1 tick per 1000 ms
const BASE_TICK_INTERVAL_MS = 1000;

// ==========================================
// MOCK STATE MANAGER (REALISTIC SIMULATION)
// ==========================================

interface MockStepState {
  id: string;
  name: string;
  q: number;           // Barang ngantre (Waiting to be processed)
  maxQ: number;        // Kapasitas maksimum meja/antrean
  processed: number;   // Barang selesai diolah, siap dikirim ke pos berikutnya
  totalProduced: number; // Akumulasi total output
  baseSpeed: number;   // Kecepatan ideal (unit per menit/tick)
  fatigueRate: number; // Kecepatan lelah berdasarkan kompleksitas Job
  isFixingError: number; // Menit tersisa untuk perbaikan cacat/human error (0 = normal)
  fatigue: number;     // 0.0 - 1.0
  stress: number;      // 0.0 - 1.0
  lastInProcess: number; // Jumlah yang sedang diproses di menit ini
  speedMultiplier: number;
}

interface MockState {
  lastTick: number;
  whStock: number;
  finalOutput: number;
  totalCost: number;
  totalErrors: number; // <-- BARU
  transfers: ActiveTransfer[];
  steps: MockStepState[];
}

let s_mockState: MockState;

function initializeMockState(): MockState {
  return {
    lastTick: -1,
    whStock: 5000,
    finalOutput: 0,
    totalCost: 0,
    totalErrors: 0,
    transfers: [],
    steps: [
      { id: "step_1", name: "Cutting", q: 0, maxQ: 100, processed: 0, totalProduced: 0, baseSpeed: 3.5, fatigueRate: 0.001, isFixingError: 0, fatigue: 0.0, stress: 0.1, lastInProcess: 0, speedMultiplier: 1.0 },
      { id: "step_2", name: "Sewing", q: 0, maxQ: 60, processed: 0, totalProduced: 0, baseSpeed: 1.8, fatigueRate: 0.0025, isFixingError: 0, fatigue: 0.0, stress: 0.1, lastInProcess: 0, speedMultiplier: 1.0 }, // Jahit lambat, cepat lelah
      { id: "step_3", name: "Quality Control", q: 0, maxQ: 50, processed: 0, totalProduced: 0, baseSpeed: 2.5, fatigueRate: 0.0015, isFixingError: 0, fatigue: 0.0, stress: 0.1, lastInProcess: 0, speedMultiplier: 1.0 },
      { id: "step_4", name: "Packing", q: 0, maxQ: 150, processed: 0, totalProduced: 0, baseSpeed: 3.0, fatigueRate: 0.0008, isFixingError: 0, fatigue: 0.0, stress: 0.1, lastInProcess: 0, speedMultiplier: 1.0 },
    ]
  };
}

// Inisialisasi awal
s_mockState = initializeMockState();

function advanceTick(state: MockState, tick: number) {
  state.lastTick = tick;
  const totalMinutes = 8 * 60 + tick; // Mulai jam 08:00
  const hour = Math.floor(totalMinutes / 60);
  const isBreak = hour === 12; // Istirahat jam 12
  const isEnded = hour >= 17;  // Pulang jam 17
  const isWorking = !isBreak && !isEnded;

  state.transfers = []; // Reset visual transfer setiap tick

  if (!isWorking) {
    // Saat istirahat, pekerja memulihkan stamina & menurunkan stres
    state.steps.forEach(s => {
      s.fatigue = Math.max(0, s.fatigue - 0.015);
      s.stress = Math.max(0, s.stress - 0.015);
      s.lastInProcess = 0;
    });
    return;
  }

  state.totalCost += 500; // Fixed cost pabrik per menit

  // 1. PROSES PRODUKSI (Mengolah Q -> Processed)
  state.steps.forEach(s => {
    // A. Logika Rework Akibat Human Error
    if (s.isFixingError > 0) {
      s.isFixingError--;
      s.lastInProcess = 0;
      s.stress = Math.min(1.0, s.stress + 0.03); // Pekerja semakin stres karena harus membongkar jahitan/memperbaiki error
      state.totalCost += 800; // Biaya kerugian material terbuang / waktu terbuang
      return; // Produksi terhenti selama proses rework
    }

    // B. Logika Kelelahan & Stres Pekerja
    s.fatigue = Math.min(1.0, s.fatigue + s.fatigueRate);
    
    // Stres naik jika barang menumpuk di mejanya (Q > 80% kapasitas)
    if (s.q > s.maxQ * 0.8) {
      s.stress = Math.min(1.0, s.stress + 0.02);
    } else {
      s.stress = Math.max(0, s.stress - 0.01);
    }

    // C. Evaluasi Peluang Human Error (Terpicu Kelelahan & Stres)
    // Base error sangat kecil (0.1%), tapi bisa naik hingga ~5% per menit jika pekerja kelelahan dan stres ekstrim.
    const errorProbability = 0.001 + (s.fatigue * 0.02) + (s.stress * 0.02);
    if (Math.random() < errorProbability) {
      s.isFixingError = Math.floor(Math.random() * 8) + 3; // Butuh 3-10 menit untuk memperbaiki human error
      state.totalErrors++;
      return; // Terjadi error! Produksi menit ini gagal.
    }

    // D. Kalkulasi Kecepatan Nyata (Terpengaruh lelah & stres)
    s.speedMultiplier = Math.max(0.4, 1.0 - (s.fatigue * 0.25) - (s.stress * 0.2));
    const actualSpeed = s.baseSpeed * s.speedMultiplier;

    // E. Pengolahan Barang
    const processAmount = Math.min(s.q, actualSpeed);
    s.q -= processAmount;
    s.lastInProcess = processAmount;
    s.processed += processAmount;
    s.totalProduced += processAmount;

    state.totalCost += 150; // Variable cost (listrik/gaji) per menit aktif
  });

  // 2. TRANSFER BARANG (Logika Back-Pressure & Kapasitas)
  
  // WH -> Step 1 (Maks 5 unit/menit, tapi dibatasi sisa kapasitas meja Cutting)
  const availableSpace0 = state.steps[0].maxQ - (state.steps[0].q + state.steps[0].processed);
  const move0 = Math.max(0, Math.min(5, availableSpace0, state.whStock));
  if (move0 > 0) {
    state.whStock -= move0;
    state.steps[0].q += move0;
    state.transfers.push({ from_step_id: "warehouse", to_step_id: "step_1", quantity: move0, unit: "Meter", batch_code: `WH-IN-${tick}` });
  }

  // Step 1 -> Step 2 (Sewing)
  const availableSpace1 = state.steps[1].maxQ - (state.steps[1].q + state.steps[1].processed);
  const move1 = Math.max(0, Math.min(state.steps[0].processed, availableSpace1));
  if (move1 > 0) {
    state.steps[0].processed -= move1;
    state.steps[1].q += move1;
    state.transfers.push({ from_step_id: "step_1", to_step_id: "step_2", quantity: move1, unit: "Pcs", batch_code: `CUT-OUT-${tick}` });
  }

  // Step 2 -> Step 3 (QC)
  const availableSpace2 = state.steps[2].maxQ - (state.steps[2].q + state.steps[2].processed);
  const move2 = Math.max(0, Math.min(state.steps[1].processed, availableSpace2));
  if (move2 > 0) {
    state.steps[1].processed -= move2;
    state.steps[2].q += move2;
    state.transfers.push({ from_step_id: "step_2", to_step_id: "step_3", quantity: move2, unit: "Pcs", batch_code: `SEW-OUT-${tick}` });
  }

  // Step 3 -> Step 4 (Packing)
  const availableSpace3 = state.steps[3].maxQ - (state.steps[3].q + state.steps[3].processed);
  const move3 = Math.max(0, Math.min(state.steps[2].processed, availableSpace3));
  if (move3 > 0) {
    state.steps[2].processed -= move3;
    state.steps[3].q += move3;
    state.transfers.push({ from_step_id: "step_3", to_step_id: "step_4", quantity: move3, unit: "Pcs", batch_code: `QC-OUT-${tick}` });
  }

  // Step 4 -> Final Output (Tidak ada batas kapasitas akhir)
  const move4 = state.steps[3].processed;
  if (move4 > 0) {
    state.steps[3].processed -= move4;
    state.finalOutput += move4;
  }
}

// --- FUNGSI MAPPING STATE KE RESPONSE JSON ---
const generateMockTick = (targetTick: number): SimulationResponse => {
  if (targetTick === 0 || targetTick < s_mockState.lastTick) {
    s_mockState = initializeMockState();
  }

  while (s_mockState.lastTick < targetTick) {
    advanceTick(s_mockState, s_mockState.lastTick + 1);
  }

  const state = s_mockState;
  const totalMinutes = 8 * 60 + state.lastTick;
  const currentHour = Math.floor(totalMinutes / 60);
  const currentMinute = totalMinutes % 60;
  
  const formattedTime = `${String(currentHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`;
  const isBreakTime = currentHour === 12;
  const isShiftEnded = currentHour >= 17;
  const currentOpStatus = isShiftEnded ? "shift_ended" : (isBreakTime ? "break" : "working");

  // Hitung jumlah pekerja yang mencapai level kritis
  const workersAtRisk = state.steps.filter(s => s.fatigue > 0.75).length; // <-- BARU

  let insight = "Alur produksi berjalan normal dan stabil.";
  const errorStep = state.steps.find(s => s.isFixingError > 0);
  const bottleneckStep = state.steps.find(s => (s.q + s.processed) > s.maxQ * 0.85);
  
  if (isShiftEnded) {
    insight = `Shift operasional selesai. Pencapaian hari ini: ${Math.round(state.finalOutput)} unit pakaian. Total insiden Human Error: ${state.totalErrors} kali.`;
  } else if (errorStep) {
    insight = `ALERT: Terjadi Human Error di pos ${errorStep.name} akibat tingkat kelelahan! Produksi terhambat selama ${errorStep.isFixingError} menit untuk proses rework/perbaikan.`;
  } else if (bottleneckStep) {
    insight = `Pos ${bottleneckStep.name} mengalami penumpukan (kritis). Hal ini memblokir suplai dari pos sebelumnya dan meningkatkan stres pekerja.`;
  }

  const jobs = ["JOB-001", "JOB-002", "JOB-003", "JOB-004"];
  const assets = ["MESIN-CUT-1", "MESIN-SEW-1", "MEJA-QC-1", "MEJA-PACK-1"];
  const units = ["Meter", "Pcs", "Pcs", "Pcs"];
  const materials = ["Kain Gulungan", "Potongan Pola", "Baju Jahitan", "Baju Lolos QC"];

  return {
    live_simulation_state: {
      shift_info: {
        current_time_formatted: formattedTime,
        current_tick_minutes: state.lastTick,
        shift_start_time: "08:00",
        shift_end_time: "17:00",
        break_start_time: "12:00",
        break_end_time: "13:00",
        operational_status: currentOpStatus,
        is_break_time: isBreakTime,
        is_shift_ended: isShiftEnded,
      },
      step_breakdown: state.steps.map((s, i) => {
        const totalWIP = s.q + s.processed;
        const fillPct = (totalWIP / s.maxQ) * 100;
        
        let nodeStatus: "normal" | "idle" | "bottleneck" = "normal";
        if (!isBreakTime && !isShiftEnded) {
          if (s.isFixingError > 0 || (s.q === 0 && s.processed === 0)) nodeStatus = "idle";
          else if (fillPct >= 85) nodeStatus = "bottleneck";
        } else {
          nodeStatus = "idle";
        }

        return {
          step_id: s.id,
          step_name: s.name,
          status: nodeStatus,
          output_generated: s.baseSpeed * 60, 
          output_per_hour: (s.baseSpeed * s.speedMultiplier) * 60, 
          total_output_produced: s.totalProduced,
          operational_cost_idr: 0, 
          speed_multiplier: s.speedMultiplier,
          wip_fill_pct: Math.min(100, fillPct),
          current_material: {
            batch_code: `BATCH-00${i + 1}`,
            material_name: materials[i],
            quantity: s.q + s.processed, 
            in_process_quantity: s.lastInProcess,
            capacity: s.maxQ,
            unit: units[i],
          }
        };
      }),
      warehouse: {
        capacity: 5000,
        current_stock: Math.max(0, state.whStock),
      },
      current_assignments: state.steps.map((s, i) => ({
        worker_id: `W-00${i + 1}`,
        assigned_job_id: jobs[i],
        assigned_asset_id: assets[i],
        calculated_realtime_metrics: {
          current_fatigue_level: s.fatigue,
          current_stress_level: s.stress,
          effective_throughput_per_hour: (s.baseSpeed * s.speedMultiplier) * 60,
          effective_error_probability: 0.001 + (s.fatigue * 0.02) + (s.stress * 0.02),
          burnout_hazard_risk: s.fatigue > 0.75 ? "high" : (s.fatigue > 0.45 ? "medium" : "low"),
          throughput_multiplier: s.speedMultiplier
        }
      })),
      active_transfers: state.transfers,
      system_bottlenecks: state.steps.filter(s => (s.q + s.processed) >= s.maxQ * 0.85).map(s => s.id),
      simulation_summary: {
        total_output_units: state.finalOutput,
        target_output_units: 500,
        production_achievement_percentage: Math.min(100, (state.finalOutput / 500) * 100),
        efficiency_score: Math.max(0, 100 - (state.steps[1].fatigue * 20)),
        total_operational_cost_idr: state.totalCost,
        cost_per_unit_idr: state.finalOutput > 0 ? state.totalCost / state.finalOutput : 0,
        // --- DATA SUMMARY BARU KITA MASUKKAN DI SINI ---
        total_human_errors: state.totalErrors,
        workers_at_risk: workersAtRisk,
      },
      analytical_insight_summary: insight,
    }
  };
};

// ==========================================
// EXPORT HOOK
// ==========================================

export function useSimulationRunner(isMock?: boolean) {
  const status = useSimulationStore((s) => s.status);
  const speedMultiplier = useSimulationStore((s) => s.speedMultiplier);
  const pause = useSimulationStore((s) => s.pause);
  const setData = useSimulationStore((s) => s.setData);
  const incrementTick = useSimulationStore((s) => s.incrementTick);
  const tick = useSimulationStore((s) => s.tick);

  const latestDataRef = useRef<SimulationResponse | null>(null);
  latestDataRef.current = useSimulationStore.getState().data;
  
  const tickRef = useRef(tick);
  useEffect(() => {
     tickRef.current = tick;
  }, [tick]);

  useEffect(() => {
    if (status !== 'running') return undefined;

    let cancelled = false;

    const runTick = async () => {
      let next: SimulationResponse;

      if (isMock) {
        // --- MOCK MODE ---
        next = generateMockTick(tickRef.current);
      } else {
        // --- REAL API MODE ---
        next = await fetchLiveSimulationState(latestDataRef.current ?? undefined);
      }
      
      if (cancelled) return;
      
      latestDataRef.current = next;
      setData(next);
      incrementTick();

      if (next.live_simulation_state.shift_info?.is_shift_ended) {
        pause();
      }
    };

    const intervalMs = BASE_TICK_INTERVAL_MS / speedMultiplier;

    runTick();
    const intervalId = window.setInterval(runTick, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [status, speedMultiplier, setData, incrementTick, pause, isMock]);
}