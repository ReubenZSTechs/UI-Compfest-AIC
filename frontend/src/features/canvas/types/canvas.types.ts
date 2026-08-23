// frontend/src/features/canvas/types/canvas.types.ts
import type { Worker, JobDesk, RealtimeMetrics } from "@/features/digital-twin/types/digitalTwin.types";
import type { Node, Edge } from "@xyflow/react";
import type { AgentChatMessage } from "@/store/agentChat";

export type CanvasNodeKind = "process" | "worker" | "output";

export type AiNodeStatus = "idle" | "analyzing" | "verified" | "error";

export type RelationType = "FLOW" | "ASSIGNED_TO";

/** Tipe Fan-Out (satu input → banyak output) pada hubungan FLOW antar proses. */
export type FlowSplitType = "serial" | "parallel";

/** Tipe Fan-In (banyak input → satu output) pada hubungan FLOW antar proses. */
export type FlowJoinType = "and" | "or";

// NOTE: dipakai sebagai tipe data Node React Flow, sehingga harus berupa
// type alias (bukan interface) agar memenuhi constraint Record<string, unknown>.

export type CanvasProcessData = {
  kind: "process";
  label: string;
  requiredSkills: string[];
  targetOutput: number;
  aiStatus: AiNodeStatus;
  jobDesk?: JobDesk | null;
};

export type CanvasWorkerData = {
  kind: "worker";
  label: string;
  worker: Worker;
  fatigueScore: number;
  aiStatus: AiNodeStatus;
  realtimeMetrics?: RealtimeMetrics | null;
};

/** Node Output = "Finished Goods Storage" (ujung alur produksi).
 *  Sesuai project.md simulation_summary: target_output_units & total_output_units. */
export type CanvasOutputData = {
  kind: "output";
  label: string;
  targetOutput: number;
  totalOutput: number;
  aiStatus: AiNodeStatus;
};

export type CanvasNodeData = CanvasProcessData | CanvasWorkerData | CanvasOutputData;

export type CanvasFlowNode = Node<CanvasNodeData, "fabric" | "worker" | "output">;

export type CanvasFlowEdgeData = {
  relation: RelationType;
  /** Hanya relevan untuk FLOW: serial (tujuan bergantian) | parallel (tujuan bersamaan). */
  flowType?: FlowSplitType;
  /** Hanya relevan untuk FLOW: and (tunggu semua) | or (jalankan saat pertama selesai). */
  joinType?: FlowJoinType;
};

export type CanvasFlowEdge = Edge<CanvasFlowEdgeData, "flow" | "assigned">;

/** Operating policy limits that constrain the AI/optimization flow. */
export interface OperationalLimits {
  /** Allow the optimizer to hire new employees when staff < demand. */
  allowRecruitNewEmployees: boolean;
  /** Allow the optimizer to schedule overtime shifts beyond regular hours. */
  allowOvertime: boolean;
  /** Allow the optimizer to outsource work to external parties. */
  allowOutsourcing: boolean;
  /** Upper budget ceiling (currency unit). 0 = no limit. */
  budgetLimit: number;
}

export type ActiveTool =
  | "select"
  | "add-process"
  | "add-worker"
  | "add-output"
  | "connect"
  | "erase"
  | "undo"
  | "redo";

export type CanvasTemplateId = "blank" | "serial" | "parallel";

export interface AnalysisRunState {
  status: "idle" | "running" | "done" | "error";
  message?: string;
  startedAt?: string;
  finishedAt?: string;
}

// ============================================================
// Sesi terpadu Live + Agent (Dashboard Project)
// ============================================================

/** Snapshot state halaman Live pada satu titik simpan. */
export interface CanvasLiveSnapshot {
  nodes: CanvasFlowNode[];
  edges: CanvasFlowEdge[];
  projectTitle: string;
  analysis: AnalysisRunState;
  operationalLimits?: OperationalLimits;
}

/** Kontrak proyek terpadu: 1 canvasId membungkus Live (liveHistory) + Agent (agentHistory). */
export interface CanvasProject {
  canvasId: string | null;
  templateId: CanvasTemplateId | null;
  name: string;
  liveHistory: CanvasLiveSnapshot[];
  agentHistory: AgentChatMessage[];
}

// ============================================================
// LLM Payload — kontrak JSON yang dikirim ke Backend/AI.
// SEMUA data visual (position, zoom, warna) TIDAK boleh ada di sini.
// ============================================================

export interface FactoryGraphNode {
  id: string;
  type: CanvasNodeKind;
  label: string;
  required_skills?: string[];
  skills?: string[];
  fatigue_score?: number;
  /** Khusus node output: target output produksi (target_output_units). */
  target_output?: number;
}

export interface FactoryGraphEdge {
  source: string;
  target: string;
  type: RelationType;
  /** Tipe alur Fan-Out (FLOW): serial | parallel. */
  flow_type?: FlowSplitType;
  /** Tipe alur Fan-In (FLOW): and | or. */
  join_type?: FlowJoinType;
}

export interface FactoryGraphPayload {
  factory_graph: {
    nodes: FactoryGraphNode[];
    edges: FactoryGraphEdge[];
  };
  /** Operational policy constraints forwarded to the AI flow. */
  operational_limits?: OperationalLimits;
}

export interface AnalyzeGraphResponse {
  status: "ok" | "error";
  message?: string;
  verified_node_ids?: string[];
  warnings?: string[];
}