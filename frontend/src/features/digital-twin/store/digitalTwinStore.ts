import { create } from "zustand";
import type { AssetCategory } from "../types/digitalTwin.types";

export type AutomationFilter = "all" | "automated" | "manual";

interface DigitalTwinState {
  // Filters — panel Asset/JobDesk
  selectedWorkflowStep: string | null;
  selectedCategory: AssetCategory | null;
  automationFilter: AutomationFilter;
  searchQuery: string;

  // Seleksi cross-highlight (dipakai nanti oleh CompatibilityMatrix)
  selectedAssetId: string | null;
  selectedWorkerId: string | null;
  selectedJobId: string | null;

  // Actions
  setSelectedWorkflowStep: (step: string | null) => void;
  setSelectedCategory: (category: AssetCategory | null) => void;
  setAutomationFilter: (filter: AutomationFilter) => void;
  setSearchQuery: (query: string) => void;
  selectAsset: (assetId: string | null) => void;
  selectWorker: (workerId: string | null) => void;
  selectJob: (jobId: string | null) => void;
  selectPair: (workerId: string, jobId: string) => void;
  resetFilters: () => void;
}

const initialFilterState = {
  selectedWorkflowStep: null,
  selectedCategory: null,
  automationFilter: "all" as AutomationFilter,
  searchQuery: "",
};

export const useDigitalTwinStore = create<DigitalTwinState>((set) => ({
  ...initialFilterState,
  selectedAssetId: null,
  selectedWorkerId: null,
  selectedJobId: null,

  setSelectedWorkflowStep: (step) => set({ selectedWorkflowStep: step }),
  setSelectedCategory: (category) => set({ selectedCategory: category }),
  setAutomationFilter: (filter) => set({ automationFilter: filter }),
  setSearchQuery: (query) => set({ searchQuery: query }),

  // Klik asset yang sama = toggle off (deselect)
  selectAsset: (assetId) =>
    set((state) => ({
      selectedAssetId: state.selectedAssetId === assetId ? null : assetId,
    })),
  selectWorker: (workerId) =>
    set((state) => ({
      selectedWorkerId: state.selectedWorkerId === workerId ? null : workerId,
    })),
  selectJob: (jobId) =>
    set((state) => ({
      selectedJobId: state.selectedJobId === jobId ? null : jobId,
    })),

  selectPair: (workerId, jobId) =>
    set((state) => {
      const isSamePair =
        state.selectedWorkerId === workerId && state.selectedJobId === jobId;
      return isSamePair
        ? { selectedWorkerId: null, selectedJobId: null }
        : { selectedWorkerId: workerId, selectedJobId: jobId };
    }),

  resetFilters: () => set(initialFilterState),
}));