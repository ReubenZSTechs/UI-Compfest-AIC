// features/simulation/store/simulationStore.ts
import { create } from 'zustand';
import { resetMockSimulationState } from '../api/simulationApi.mock';
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
  reset: () => void;
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
  reset: () => {
    resetMockSimulationState(); // mock-only: clears batch/progress state; remove once backend-backed
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