// frontend/src/features/project/types/project.types.ts
// Skema tunggal terpadu untuk satu Project/Draft session.
// Satu objek ini membungkus SELURUH alur kerja:
//   Template → Live/Agent Canvas → Optimization Cards (recommendations).
// Digunakan sebagai satu-satunya sumber kebenaran untuk persistensi
// (localStorage via zustand persist + backup best-effort ke backend).
import type { AgentChatMessage } from "@/store/agentChat";
import type {
  CanvasFlowEdge,
  CanvasFlowNode,
  CanvasTemplateId,
  OperationalLimits,
} from "@/features/canvas/types/canvas.types";

/** Tahap aktif alur kerja — dipakai untuk resume saat draft dibuka lagi. */
export type ProjectStep = "canvas" | "agent" | "recommendations";

/** Satu kartu rekomendasi optimasi yang digenerate AI. */
export interface OptimizationCard {
  id: string;
  title: string;
  budget: number;
  description: string;
}

export interface OptimizationData {
  generatedCards: OptimizationCard[];
  selectedCardId: string | null;
}

/** Dokumen terpadu satu proyek/draft (lihat requirement JSON di atas). */
export interface ProjectDraft {
  projectId: string;
  templateId: CanvasTemplateId;
  title: string;
  currentStep: ProjectStep;
  lastUpdated: string;
  createdAt: string;
  canvasData: {
    nodes: CanvasFlowNode[];
    edges: CanvasFlowEdge[];
  };
  liveData: {
    chatHistory: AgentChatMessage[];
  };
  agentData: {
    chatHistory: AgentChatMessage[];
    operationalSettings: OperationalLimits;
  };
  optimizationData: OptimizationData;
}
