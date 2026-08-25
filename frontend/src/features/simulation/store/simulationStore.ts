import { create } from 'zustand';
import { resetMockSimulationState, getSimulationConfig } from '../api/simulationApi';
import type { SimulationResponse, SimulationRunStatus } from '../types/simulation.types';

export type SpeedMultiplier = 1 | 2 | 5 | 10;

interface SimulationStore {
  status: SimulationRunStatus;
  data: SimulationResponse | null;
  tick: number;
  selectedStepId: string | null;
  speedMultiplier: SpeedMultiplier;
  error: string | null;
  start: () => void;
  pause: () => void;
  reset: () => Promise<void>;
  setData: (data: SimulationResponse) => void;
  setError: (message: string | null) => void;
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
  error: null,

  start: () => set({ status: 'running', error: null }),
  pause: () => set({ status: 'paused' }),

  reset: async () => {
    try {
      const config = await getSimulationConfig();
      resetMockSimulationState(config);
      set({
        status: 'idle',
        data: null,
        tick: 0,
        selectedStepId: null,
        speedMultiplier: 1,
        error: null,
      });
    } catch (error) {
      set({
        status: 'idle',
        data: null,
        tick: 0,
        selectedStepId: null,
        error:
          error instanceof Error
            ? error.message
            : 'Konfigurasi simulasi tidak dapat dimuat.',
      });
    }
  },

  setData: (data) => set({ data }),
  setError: (message) => set({ error: message }),
  incrementTick: () => set((s) => ({ tick: s.tick + 1 })),
  selectStep: (stepId) =>
    set((s) => ({ selectedStepId: s.selectedStepId === stepId ? null : stepId })),
  setSpeedMultiplier: (speed) => set({ speedMultiplier: speed }),
}));