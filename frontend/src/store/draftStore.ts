// frontend/src/store/draftStore.ts
// Store terpusat tunggal untuk Project/Draft session (unified schema).
//
// - `drafts`: registry semua draft tersimpan (ditampilkan di Dashboard).
// - `activeDraftId`: draft yang sedang dibuka di global project context.
// - Setiap perubahan state kerja (canvas nodes/edges, chat, operational
//   settings, optimization cards) disinkronkan ke SATU record ProjectDraft
//   via syncActiveDraft() (dipanggil oleh useDraftAutoSync) lalu dipersist
//   otomatis ke localStorage (zustand persist).
// - Migrasi otomatis dari penyimpanan lama (canvas-projects-v2) bila ada.
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useAgentChatStore } from "@/store/agentChat";
import {
  CANVAS_TEMPLATES
} from "@/features/canvas/templates/templates";
import type { CanvasTemplateId, CanvasFactoryMeta, CanvasSimulationSettings } from "@/features/canvas/types/canvas.types";
import type {
  OptimizationCard,
  ProjectDraft,
  ProjectStep,
} from "@/features/project/types/project.types";

const STORAGE_KEY = "pabrikers-drafts-v1";
const LEGACY_PROJECTS_KEY = "canvas-projects-v2";

const DEFAULT_LIMITS = {
  allowRecruitNewEmployees: false,
  allowOvertime: false,
  allowOutsourcing: false,
  budgetLimit: 0,
} as const;

/** Membuat projectId unik untuk satu draft. */
export function createProjectId(): string {
  return `proj_draft_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

/** Konversi record Dashboard lama (canvas-projects-v2) → ProjectDraft. */
function migrateLegacyV2(): ProjectDraft[] {
  try {
    if (localStorage.getItem(STORAGE_KEY)) return [];
    const raw = localStorage.getItem(LEGACY_PROJECTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Array<Record<string, unknown>>;
    if (!Array.isArray(parsed)) return [];

    const drafts: ProjectDraft[] = [];
    for (const p of parsed) {
      const canvasId = typeof p.canvasId === "string" ? p.canvasId : null;
      const history = Array.isArray(p.liveHistory) ? (p.liveHistory as Array<Record<string, unknown>>) : [];
      const snap = history[history.length - 1];
      if (!canvasId || !snap) continue;

      drafts.push({
        projectId: canvasId,
        templateId: (p.templateId as ProjectDraft["templateId"]) ?? "blank",
        factoryId: null, // Legacy drafts won't have a factoryId initially
        title: typeof p.name === "string" ? p.name : "Proyek Pabrik Tanpa Judul",
        currentStep: "canvas",
        lastUpdated: typeof p.updatedAt === "string" ? p.updatedAt : new Date().toISOString(),
        createdAt: typeof p.createdAt === "string" ? p.createdAt : new Date().toISOString(),
        canvasData: {
          nodes: (snap.nodes as ProjectDraft["canvasData"]["nodes"]) ?? [],
          edges: (snap.edges as ProjectDraft["canvasData"]["edges"]) ?? [],
          // Providing empty defaults for the new fields on legacy items
          factoryMeta: (snap.factoryMeta as ProjectDraft["canvasData"]["factoryMeta"]) ?? {},
          shifts: [],
          simulationSettings: {} as any,
          workerPool: [],
          workerAssignments: {},
        },
        liveData: { chatHistory: [] },
        agentData: {
          chatHistory: (p.agentHistory as ProjectDraft["agentData"]["chatHistory"]) ?? [],
          operationalSettings: (snap.operationalLimits as ProjectDraft["agentData"]["operationalSettings"]) ?? { ...DEFAULT_LIMITS },
        },
        optimizationData: { generatedCards: [], selectedCardId: null },
      });
    }

    if (drafts.length > 0) {
      localStorage.removeItem(LEGACY_PROJECTS_KEY);
    }
    return drafts;
  } catch {
    return [];
  }
}

interface DraftState {
  drafts: ProjectDraft[];
  activeDraftId: string | null;

  findDraft: (projectId: string) => ProjectDraft | undefined;
  getActiveDraft: () => ProjectDraft | null;

  /** Buat draft baru dari template, aktifkan, dan hydrate working state. */
  createDraft: (templateId: CanvasTemplateId, meta: CanvasFactoryMeta) => string;
    /** Muat draft ke global project context (hydrate canvas + chats + cards). */
  loadDraft: (projectId: string) => void;
  deleteDraft: (projectId: string) => void;
  duplicateDraft: (projectId: string) => ProjectDraft | null;
  applyLegacyDraft: (draft: ProjectDraft) => void;

  setTitle: (title: string) => void;
  setCurrentStep: (step: ProjectStep) => void;
  setOperationalSettings: (settings: ProjectDraft["agentData"]["operationalSettings"]) => void;
  setOptimizationCards: (cards: OptimizationCard[]) => void;
  selectOptimizationCard: (cardId: string | null) => void;
  setFactoryId: (factoryId: string | null) => void;

  /** Mirror working state (canvasUI + agentChat) ke active draft + persist. */
  syncActiveDraft: () => void;
  saveActiveDraft: () => Promise<void>;
}

export const useDraftStore = create<DraftState>()(
  persist(
    (set, get) => {
      /** Update record aktif + bump lastUpdated + taruh di urutan teratas. */
      function updateActive(patch: Partial<ProjectDraft>) {
        const { drafts, activeDraftId } = get();
        const current = drafts.find((d) => d.projectId === activeDraftId);
        if (!current) return;
        const updated: ProjectDraft = {
          ...current,
          ...patch,
          lastUpdated: new Date().toISOString(),
        };
        set({
          drafts: [updated, ...drafts.filter((d) => d.projectId !== current.projectId)],
        });
      }

      return {
        drafts: migrateLegacyV2(),
        activeDraftId: null,

        findDraft: (projectId) => get().drafts.find((d) => d.projectId === projectId),

        getActiveDraft: () => {
          const { drafts, activeDraftId } = get();
          return drafts.find((d) => d.projectId === activeDraftId) ?? null;
        },

        createDraft: (templateId, meta) => {
          const projectId = createProjectId();
          const { nodes, edges } = CANVAS_TEMPLATES[templateId]();
          const now = new Date().toISOString();
          const draft: ProjectDraft = {
            projectId,
            templateId,
            factoryId: null,
            title: meta.factoryName,
            currentStep: "canvas",
            lastUpdated: now,
            createdAt: now,
            canvasData: {
              nodes,
              edges,
              factoryMeta: meta,
              shifts: [{ shiftId: "shift-01", startTime: "08:00", endTime: "16:00" }],
              simulationSettings: {} as CanvasSimulationSettings,
              workerPool: [],
              workerAssignments: {},
            },
            liveData: { chatHistory: [] },
            agentData: { chatHistory: [], operationalSettings: { ...DEFAULT_LIMITS } },
            optimizationData: { generatedCards: [], selectedCardId: null },
          };

          const canvas = useCanvasUIStore.getState();
          canvas.loadTemplate(nodes, edges);
          canvas.setProjectTitle(draft.title);
          canvas.setAnalysis({ status: "idle" });
          canvas.setSession(projectId, templateId);
          canvas.hydrateCanvasMeta({
            factoryId: null,
            factoryMeta: meta,
            shifts: draft.canvasData.shifts,
            simulationSettings: draft.canvasData.simulationSettings,
            workerPool: [],
            workerAssignments: {},
          });
          useAgentChatStore.getState().startNewSession(projectId);

          set((s) => ({ drafts: [draft, ...s.drafts], activeDraftId: projectId }));
          return projectId;
        },

        loadDraft: (projectId) => {
          const draft = get().findDraft(projectId);
          if (!draft) return;

          // Re-hydrate seluruh state kerja dari satu record draft.
          const canvas = useCanvasUIStore.getState();
          canvas.loadTemplate(draft.canvasData.nodes, draft.canvasData.edges);
          canvas.setProjectTitle(draft.title);
          canvas.setAnalysis({ status: "idle" });
          canvas.setSession(draft.projectId, draft.templateId);
          canvas.applyOperationalLimits(draft.agentData.operationalSettings);
          
          canvas.hydrateCanvasMeta({
            factoryId: draft.factoryId,
            factoryMeta: draft.canvasData.factoryMeta,
            shifts: draft.canvasData.shifts,
            simulationSettings: draft.canvasData.simulationSettings,
            workerPool: draft.canvasData.workerPool,
            workerAssignments: draft.canvasData.workerAssignments,
          });

          useAgentChatStore.getState().hydrate(
            draft.projectId,
            draft.agentData.chatHistory
          );

          set({ activeDraftId: projectId });
        },

        deleteDraft: (projectId) => {
          set((s) => ({
            drafts: s.drafts.filter((d) => d.projectId !== projectId),
            activeDraftId: s.activeDraftId === projectId ? null : s.activeDraftId,
          }));
        },

        duplicateDraft: (projectId) => {
          const src = get().findDraft(projectId);
          if (!src) return null;
          const now = new Date().toISOString();
          const copy: ProjectDraft = {
            ...src,
            projectId: createProjectId(),
            title: `${src.title} (Salinan)`,
            currentStep: "canvas",
            createdAt: now,
            lastUpdated: now,
          };
          set((s) => ({ drafts: [copy, ...s.drafts] }));
          return copy;
        },

        applyLegacyDraft: (draft) => {
          set((s) => {
            if (s.drafts.some((d) => d.projectId === draft.projectId)) return s;
            return { drafts: [draft, ...s.drafts] };
          });
        },

        setTitle: (title) => updateActive({ title }),

        setCurrentStep: (step) => updateActive({ currentStep: step }),

        setOperationalSettings: (settings) => {
          const agentData = get().getActiveDraft()?.agentData;
          if (!agentData) return;
          updateActive({ agentData: { ...agentData, operationalSettings: settings } });
        },

        setOptimizationCards: (cards) =>
          updateActive({ optimizationData: { generatedCards: cards, selectedCardId: null } }),

        selectOptimizationCard: (cardId) => {
          const optimizationData = get().getActiveDraft()?.optimizationData;
          if (!optimizationData) return;
          updateActive({
            optimizationData: { ...optimizationData, selectedCardId: cardId },
          });
        },

        setFactoryId: (factoryId: string | null) => {
          useCanvasUIStore.getState().setFactoryId(factoryId);
          updateActive({ factoryId });
        },

        syncActiveDraft: () => {
          const active = get().getActiveDraft();
          if (!active) return;
          const canvas = useCanvasUIStore.getState();
          const chat = useAgentChatStore.getState();
          updateActive({
            title: canvas.projectTitle,
            factoryId: canvas.factoryId,
            canvasData: {
              nodes: canvas.nodes,
              edges: canvas.edges,
              factoryMeta: canvas.factoryMeta,
              shifts: canvas.shifts,
              simulationSettings: canvas.simulationSettings,
              workerPool: canvas.workerPool,
              workerAssignments: canvas.workerAssignments,
            },
            liveData: { chatHistory: chat.messages },
            agentData: {
              chatHistory: chat.messages,
              operationalSettings: canvas.operationalLimits,
            },
          });
        },

        saveActiveDraft: async () => {
          get().syncActiveDraft();
        },
      };
    },
    {
      name: STORAGE_KEY,
      partialize: (state) => ({
        drafts: state.drafts,
        activeDraftId: state.activeDraftId,
      }),
    }
  )
);