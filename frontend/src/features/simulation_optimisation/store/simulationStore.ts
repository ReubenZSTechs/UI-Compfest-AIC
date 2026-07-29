// features/simulation/store/simulationStore.ts
import { create } from 'zustand';
import type { SimulationResponse, SimulationRunStatus } from '../types/simulation.types';

interface SimulationStore {
  status: SimulationRunStatus;
  data: SimulationResponse | null;
  tick: number;
  selectedStepId: string | null;

  start: () => void;
  pause: () => void;
  reset: () => void;
  setData: (data: SimulationResponse) => void;
  incrementTick: () => void;
  selectStep: (stepId: string | null) => void;
}

export const useSimulationStore = create<SimulationStore>((set) => ({
  status: 'idle',
  data: null,
  tick: 0,
  selectedStepId: null,

  start: () => set({ status: 'running' }),
  pause: () => set({ status: 'paused' }),
  reset: () => set({ status: 'idle', data: null, tick: 0, selectedStepId: null }),
  setData: (data) => set({ data }),
  incrementTick: () => set((s) => ({ tick: s.tick + 1 })),
  selectStep: (stepId) => set((s) => ({ selectedStepId: s.selectedStepId === stepId ? null : stepId })),
}));