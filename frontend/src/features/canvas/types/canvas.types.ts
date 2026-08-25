// frontend/src/features/canvas/types/canvas.types.ts
import type { Worker, JobDesk, RealtimeMetrics } from "@/features/digital-twin/types/digitalTwin.types";
import type { Node, Edge } from "@xyflow/react";
import type { AgentChatMessage } from "@/store/agentChat";

export type CanvasNodeKind = "process" | "worker" | "output" | "warehouse";

export type AiNodeStatus = "idle" | "analyzing" | "verified" | "error";

export type RelationType = "FLOW" | "ASSIGNED_TO";

/** Tipe Fan-Out (satu input → banyak output) pada hubungan FLOW antar proses. */
export type FlowSplitType = "serial" | "parallel";

/** Tipe Fan-In (banyak input → satu output) pada hubungan FLOW antar proses. */
export type FlowJoinType = "and" | "or";

// NOTE: dipakai sebagai tipe data Node React Flow, sehingga harus berupa
// type alias (bukan interface) agar memenuhi constraint Record<string, unknown>.
export type AutomationLevel = "manual" | "semi_automated" | "automated";
export type HazardLevel = "low" | "medium" | "high";
export type UnitClass = "mass" | "volume" | "count" | "power" | "noise";
export type ErrorSeverityLevel = "low" | "moderate" | "high" | "critical";

export type CanvasAssetCategory =
  | "machine"
  | "measuring_equipment"
  | "conveyor_automation"
  | "environmental_chamber"
  | "manual_station";

export interface CanvasQuantity {
  value: number | null;
  unit: string | null;
  unitClass: UnitClass | null;
  basis: string | null;
}

export interface CanvasEnvironmentalFactors {
  powerConsumptionWatt: number | null;
  noiseLevelDb: number | null;
  vibrationHazardLevel: HazardLevel;
  physicalStrainIndex: number;
}

export interface CanvasAssetSpec {
  assetId: string;
  assetName: string;
  category: CanvasAssetCategory;
  unitsAvailable: number;
  capacityPerUnit: CanvasQuantity;
  totalCapacity: CanvasQuantity;
  automationLevel: AutomationLevel;
  isAutomated: boolean;
  operationalCostPerHour: number;
  currency: string;
  environmentalFactors: CanvasEnvironmentalFactors;
}

export interface CanvasStageSpec {
  stageId: string;
  lane: string;
  operatorTask: string;
  flowType: "batch" | "continuous";
  cycleTimeSeconds: number;
  throughput: CanvasQuantity;
  throughputPerHour: number | null;
  automationLevel: AutomationLevel;
  qcRequirement: string;
  materialInput: string[];
  materialOutput: string[];
  materialPerBatch: CanvasQuantity[];
}

export interface CanvasJobDemands {
  requiredCognitiveFocus: number;
  physicalDemandLevel: HazardLevel;
  taskComplexity: number;
  errorSeverity: ErrorSeverityLevel;
}

export interface CanvasJobSpec {
  jobId: string;
  jobTitle: string;
  shiftId: string;
  headcount: number;
  demands: CanvasJobDemands;
  qcRequirement: string;
}

export interface CanvasStationSpec {
  materialName: string;
  materialUnit: string;
  stepCostBase: number;
  capacity: number;
  batchIn: number;
  batchOut: number;
  cycleTicks: number;
}

export interface CanvasShiftBreak {
  breakId: string;
  label: string;
  startOffsetMinutes: number;
  durationMinutes: number;
}

export interface CanvasShift {
  shiftId: string;
  shiftName: string;
  startTime: string;
  endTime: string;
  handoverMinutes: number;
  breaks: CanvasShiftBreak[];
}

export interface ShiftNodeAssignment {
  shiftId: string;
  nodeId: string;
  workerIds: string[];
}

export type ShiftAssignmentMap = Record<string, Record<string, string[]>>;

export interface CanvasFactoryMeta {
  factoryName: string;
  processType: "serial" | "parallel" | "hybrid";
  layoutDescription: string;
  declaredWorkerCount: number;
}

export interface CanvasSimulationSettings {
  bottleneckFillThreshold: number;
  idleQtyThreshold: number;
  station1SafetyMargin: number;
  warehouseCapacity: number;
  warehouseFeedRate: number;
  shiftStartMinutes: number;
  breakStartElapsed: number;
  breakEndElapsed: number;
  shiftEndElapsed: number;
  targetOutputUnits: number;
  initialBatchSeq: number;
  analyticalInsightSummary: string;
}

export interface CanvasWorkerProfile {
  workerId: string;
  name: string;
  skills: string[];
  certifications: string[];
  capabilities: string[];
  demographics: Record<string, unknown>;
  shiftContext: Record<string, unknown>;
  sourceFile?: string;
}

export type WorkerUploadStatus = "idle" | "uploading" | "success" | "error";

export interface WorkerUploadState {
  status: WorkerUploadStatus;
  fileName: string | null;
  message: string | null;
  acceptedCount: number;
  rejectedCount: number;
}

export type BuildStageId =
  | "autofill"
  | "factory"
  | "workers"
  | "design"
  | "compatibility"
  | "done";

export type BuildStageStatus = "pending" | "active" | "success" | "error";

export interface CanvasBuildProgress {
  stage: BuildStageId;
  status: BuildStageStatus;
  message: string | null;
}

export type CanvasProcessData = {
  kind: "process";
  label: string;
  requiredSkills: string[];
  targetOutput: number;
  aiStatus: AiNodeStatus;
  autoFields?: NodeFieldModes;
  jobDesk?: JobDesk | null;
  stage?: CanvasStageSpec;
  asset?: CanvasAssetSpec;
  job?: CanvasJobSpec;
  station?: CanvasStationSpec;
};

export type CanvasWorkerData = {
  kind: "worker";
  label: string;
  worker: Worker;
  fatigueScore: number;
  aiStatus: AiNodeStatus;
  realtimeMetrics?: RealtimeMetrics | null;
};

/** Node Output = "Finished Goods Storage" (ujung alur produksi). */
export type CanvasOutputData = {
  kind: "output";
  label: string;
  targetOutput: number;
  totalOutput: number;
  materialName: string;
  materialUnit: string;
  acceptsDefective: boolean;
  aiStatus: AiNodeStatus;
};

export type WarehouseSupplyMode = "finite" | "continuous";

export interface CanvasWarehouseItem {
  itemId: string;
  materialName: string;
  materialUnit: string;
  quantityPerFeed: number;
}

export type CanvasWarehouseData = {
  kind: "warehouse";
  label: string;
  capacity: number;
  feedRate: number;
  materialName: string;
  materialUnit: string;
  supplyMode: WarehouseSupplyMode;
  initialStock: number;
  replenishPerTick: number;
  outputItems: CanvasWarehouseItem[];
  aiStatus: AiNodeStatus;
};

export type CanvasNodeData =   
  | CanvasProcessData
  | CanvasWorkerData
  | CanvasOutputData
  | CanvasWarehouseData;

export type CanvasFlowNode = Node<CanvasNodeData, "fabric" | "worker" | "output" | "warehouse">;

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
  | "add-warehouse"
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

// ============================================================
// Autofill Types
// ============================================================

export type FieldFillMode = "manual" | "auto";

export type AutofillFieldKey =
  | "requiredSkills"
  | "operatorTask"
  | "qcRequirement"
  | "materialInput"
  | "materialOutput"
  | "cycleTimeSeconds"
  | "lane"
  | "jobTitle"
  | "headcount"
  | "demands";

export type NodeFieldModes = Partial<Record<AutofillFieldKey, FieldFillMode>>;

export type AutofillField =
  | "operatorTask"
  | "qcRequirement"
  | "requiredSkills"
  | "materialInput"
  | "materialOutput"
  | "cycleTimeSeconds"
  | "headcount"
  | "lane"
  | "jobTitle"
  | "demands";

export interface NodeAutofillSuggestions {
  operatorTask?: string | null;
  qcRequirement?: string | null;
  requiredSkills?: string[] | null;
  materialInput?: string[] | null;
  materialOutput?: string[] | null;
  materialName?: string | null;
  materialUnit?: string | null;
  cycleTimeSeconds?: number | null;
  capacity?: number | null;
  batchIn?: number | null;
  batchOut?: number | null;
  cycleTicks?: number | null;
  headcount?: number | null;
  lane?: string | null;
  jobTitle?: string | null;
}

export interface NodeAutofillRequest {
  processName: string;
  operatorTask: string;
  jobTitle: string;
  requiredSkills: string[];
  qcRequirement: string;
  assetCategory: CanvasAssetCategory;
  automationLevel: AutomationLevel;
  cycleTimeSeconds: number;
  noiseLevelDb: number | null;
  physicalStrainIndex: number;
  materialInput: string[];
  materialOutput: string[];
  headcount: number;
  upstreamNames: string[];
  downstreamNames: string[];
  targetFields: string[];
}

export interface NodeAutofillResponse {
  demands: CanvasJobDemands;
  suggestions: NodeAutofillSuggestions;
  reasoning: string;
}