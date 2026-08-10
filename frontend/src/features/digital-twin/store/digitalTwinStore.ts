import { create } from "zustand";
import { digitalTwinApi } from "../api/digitalTwinApi";
import type { DigitalTwin, AssetCategory } from "../types/digitalTwin.types";

export type AutomationFilter = "all" | "automated" | "manual";

interface DigitalTwinState {
  // Data & fetch lifecycle
  data: DigitalTwin | null;
  isLoading: boolean;
  error: Error | null;
  simulationId?: string;
  fetchTwin: (simulationId?: string) => Promise<void>;

  // Filter bar (global)
  searchQuery: string;
  selectedWorkflowStep: string | null;
  selectedCategory: AssetCategory | null;
  automationFilter: AutomationFilter;

  setSearchQuery: (query: string) => void;
  setSelectedWorkflowStep: (step: string | null) => void;
  setSelectedCategory: (category: AssetCategory | null) => void;
  setAutomationFilter: (filter: AutomationFilter) => void;
  resetFilters: () => void;

  // Seleksi per-entity
  selectedAssetId: string | null;
  selectedWorkerId: string | null;
  selectedJobId: string | null;

  selectAsset: (assetId: string) => void;
  selectWorker: (workerId: string) => void;
  selectJob: (jobId: string) => void;
  /** Dipakai CompatibilityMatrix: set worker+job sekaligus saat sel diklik */
  selectPair: (workerId: string, jobId: string) => void;
}

export const useDigitalTwinStore = create<DigitalTwinState>((set) => ({
  data: null,
  isLoading: false,
  error: null,
  simulationId: undefined,

  fetchTwin: async (simulationId?: string) => {
    set({ isLoading: true, error: null, simulationId });
    try {
      const response = await digitalTwinApi.getFullTwin(simulationId);
      // Memastikan data bernilai null jika API mengembalikan null/undefined
      set({ data: response ?? null, isLoading: false });
    } catch (err) {
      set({
        data: null, // Reset data ke null jika request gagal
        error: err instanceof Error ? err : new Error("Gagal memuat digital twin"),
        isLoading: false,
      });
    }
  },

  searchQuery: "",
  selectedWorkflowStep: null,
  selectedCategory: null,
  automationFilter: "all",

  setSearchQuery: (query) => set({ searchQuery: query }),
  setSelectedWorkflowStep: (step) => set({ selectedWorkflowStep: step }),
  setSelectedCategory: (category) => set({ selectedCategory: category }),
  setAutomationFilter: (filter) => set({ automationFilter: filter }),
  resetFilters: () =>
    set({
      searchQuery: "",
      selectedWorkflowStep: null,
      selectedCategory: null,
      automationFilter: "all",
      selectedAssetId: null,
      selectedWorkerId: null,
      selectedJobId: null,
    }),

  selectedAssetId: null,
  selectedWorkerId: null,
  selectedJobId: null,

  selectAsset: (assetId) =>
    set((s) => ({ selectedAssetId: s.selectedAssetId === assetId ? null : assetId })),
  selectWorker: (workerId) =>
    set((s) => ({ selectedWorkerId: s.selectedWorkerId === workerId ? null : workerId })),
  selectJob: (jobId) =>
    set((s) => ({ selectedJobId: s.selectedJobId === jobId ? null : jobId })),
  selectPair: (workerId, jobId) =>
    set((s) => ({
      selectedWorkerId: s.selectedWorkerId === workerId && s.selectedJobId === jobId ? null : workerId,
      selectedJobId: s.selectedWorkerId === workerId && s.selectedJobId === jobId ? null : jobId,
    })),
}));