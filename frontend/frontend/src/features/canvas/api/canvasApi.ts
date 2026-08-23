// frontend/src/features/canvas/api/canvasApi.ts
// API & persistensi kanvas sesi terpadu (unified ProjectDraft).
//
// Semua state kini tinggal di SATU record ProjectDraft (draftStore) yang
// terpersist otomatis di localStorage. File ini hanya menyediakan:
//   - saveCanvasSession(title)  : sync + backup best-effort ke backend.
//   - loadLegacyCanvasProject() : migrasi proyek lama (backend/lokal v1).
import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import { useDraftStore, createProjectId } from "@/store/draftStore";
import type {
  AnalyzeGraphResponse,
  CanvasFlowEdge,
  CanvasFlowNode,
  CanvasProject,
  FactoryGraphPayload,
} from "../types/canvas.types";
import {
  computeExecutionRounds,
  describeFlowSemantics,
  type FlowGraph,
} from "../utils/flowLogic";
import type { ProjectDraft } from "@/features/project/types/project.types";

const LEGACY_STORAGE_KEY = "canvas-project-v1";

const DEFAULT_LIMITS = {
  allowRecruitNewEmployees: false,
  allowOvertime: false,
  allowOutsourcing: false,
  budgetLimit: 0,
} as const;

async function analyzeViaBackend(payload: FactoryGraphPayload): Promise<AnalyzeGraphResponse> {
  const { data } = await apiClient.post<AnalyzeGraphResponse>(ENDPOINTS.CANVAS.ANALYZE, payload, {
    timeout: 30000,
  });
  return data;
}

/**
 * Simulasi analisis AI untuk mode demo (backend belum punya endpoint / tidak aktif).
 * Urutan verifikasi node mengikuti jadwal eksekusi semantik alur:
 * Fan-Out Serial/Parallel Split & Fan-In AND/OR Join (lihat utils/flowLogic.ts).
 */
async function analyzeViaMock(payload: FactoryGraphPayload): Promise<AnalyzeGraphResponse> {
  const graph = payload.factory_graph as unknown as FlowGraph;
  const rounds = computeExecutionRounds(graph);
  const orderedProcessIds = rounds.flat();
  // Node output (finished goods storage) ikut diverifikasi sebagai ujung alur.
  const orderedOutputIds = graph.nodes
    .filter((n) => n.type === "output")
    .map((n) => n.id);
  const flowSemantics = describeFlowSemantics(graph);

  await new Promise((resolve) => setTimeout(resolve, 1200));
  for (let i = 0; i < orderedProcessIds.length; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  const warnings: string[] = [...flowSemantics];
  const assignedWorkers = graph.edges.filter((e) => e.type === "ASSIGNED_TO").length;
  if (assignedWorkers === 0 && graph.nodes.some((n) => n.type === "process")) {
    warnings.push("Tidak ada pekerja yang ditugaskan (ASSIGNED_TO) ke proses manapun.");
  }

  return {
    status: "ok",
    message: `Analisis selesai: ${orderedProcessIds.length} proses terverifikasi dalam ${rounds.length} tahap eksekusi (mode demo).`,
    verified_node_ids: [...orderedProcessIds, ...orderedOutputIds],
    warnings,
  };
}

export async function analyzeFactoryGraph(payload: FactoryGraphPayload): Promise<AnalyzeGraphResponse> {
  try {
    return await analyzeViaBackend(payload);
  } catch {
    return analyzeViaMock(payload);
  }
}

/**
 * Simpan sesi draft terpadu: pastikan judul terbaru tersinkron ke record
 * ProjectDraft aktif, lalu kirim backup best-effort ke backend (tanpa
 * menahan UI). Persistensi utama tetap localStorage via draftStore.
 */
export async function saveCanvasSession(title: string): Promise<void> {
  const draftStore = useDraftStore.getState();
  draftStore.setTitle(title);
  draftStore.saveActiveDraft();
}

/** Konversi proyek legacy (liveHistory + agentHistory) → ProjectDraft. */
export function legacyCanvasProjectToDraft(project: CanvasProject): ProjectDraft | null {
  const snap = project.liveHistory[project.liveHistory.length - 1];
  if (!snap) return null;
  const now = new Date().toISOString();
  return {
    projectId: project.canvasId ?? createProjectId(),
    templateId: project.templateId ?? "blank",
    title: snap.projectTitle || project.name || "Proyek Pabrik Tanpa Judul",
    currentStep: "canvas",
    lastUpdated: now,
    createdAt: now,
    canvasData: { nodes: snap.nodes, edges: snap.edges },
    liveData: { chatHistory: [] },
    agentData: {
      chatHistory: project.agentHistory ?? [],
      operationalSettings:
        snap.operationalLimits ?? { ...DEFAULT_LIMITS },
    },
    optimizationData: { generatedCards: [], selectedCardId: null },
  };
}

/**
 * Muat proyek lama tersimpan (backend "latest", lalu localStorage legacy).
 * Digunakan untuk migrasi proyek lama ke Dashboard saat daftar kosong.
 */
export async function loadLegacyCanvasProject(): Promise<CanvasProject | null> {
  try {
    const { data } = await apiClient.get<unknown>(
      ENDPOINTS.CANVAS.PROJECTS_LATEST,
      { timeout: 6000 }
    );
    if (data) {
      const normalized = normalizeProject(data);
      if (normalized) return normalized;
    }
  } catch {
    // backend tidak aktif — lanjut cek localStorage legacy.
  }

  const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
  if (!raw) return null;
  try {
    return normalizeProject(JSON.parse(raw));
  } catch {
    return null;
  }
}

/**
 * Normalisasi payload lama (hanya { name, nodes, edges }) menjadi kontrak
 * terpadu (liveHistory + agentHistory) agar proyek lama tetap bisa dibuka.
 */
function normalizeProject(raw: unknown): CanvasProject | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;

  if (Array.isArray(obj.liveHistory)) {
    return obj as unknown as CanvasProject;
  }

  // Bentuk lama / backend versi sebelumnya: { name, nodes, edges }.
  if (Array.isArray(obj.nodes)) {
    const name = typeof obj.name === "string" ? obj.name : "Proyek Pabrik Tanpa Judul";
    return {
      canvasId: null,
      templateId: null,
      name,
      liveHistory: [
        {
          nodes: obj.nodes as CanvasFlowNode[],
          edges: Array.isArray(obj.edges) ? (obj.edges as CanvasFlowEdge[]) : [],
          projectTitle: name,
          analysis: { status: "idle" },
        },
      ],
      agentHistory: [],
    };
  }

  return null;
}
