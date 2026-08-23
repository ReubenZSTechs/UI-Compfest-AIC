// features/simulation/store/simulationStore.ts
import { create } from 'zustand';
import { resetMockSimulationState, getSimulationConfig } from '../api/simulationApi'; // ganti dari .mock
import type { SimulationResponse, SimulationRunStatus } from '../types/simulation.types';

export type SpeedMultiplier = 1 | 2 | 5 | 10;

interface SimulationStore {
  status: SimulationRunStatus;
  data: SimulationResponse | null;
  tick: number;
  selectedStepId: string | null;
  speedMultiplier: SpeedMultiplier;
  start: () => void;
  pause: () => void;
  reset: () => Promise<void>; // <-- signature berubah jadi async
  setData: (data: SimulationResponse) => void;
  incrementTick: () => void;
  selectStep: (stepId: string | null) => void;
  setSpeedMultiplier: (speed: SpeedMultiplier) => void;
}

export const useSimulationStore = create<SimulationStore>((set) => ({
  status: 'idle',
  data: null,
  tick: 0,
  selectedStepId: null,
  speedMultiplier: 1,
  start: () => set({ status: 'running' }),
  pause: () => set({ status: 'paused' }),
  reset: async () => {
    // Config sudah pernah di-fetch waktu load awal (cached di modul
    // simulationApi.ts), jadi panggilan ini biasanya instan -- tidak
    // nge-fetch ulang ke backend.
    const config = await getSimulationConfig();
    resetMockSimulationState(config);
    set({
      status: 'idle',
      data: null,
      tick: 0,
      selectedStepId: null,
      speedMultiplier: 1,
    });
  },
  setData: (data) => set({ data }),
  incrementTick: () => set((s) => ({ tick: s.tick + 1 })),
  selectStep: (stepId) => set((s) => ({ selectedStepId: s.selectedStepId === stepId ? null : stepId })),
  setSpeedMultiplier: (speed) => set({ speedMultiplier: speed }),
}));