// frontend/src/store/canvasUI.ts
// Visual State Canvas Workspace: activeTool, node/edge graph, undo/redo stack.
// CATATAN: State ini MURNI visual — koordinat & zoom TIDAK pernah dikirim ke AI.
// Lihat src/features/canvas/utils/graphExtractor.ts untuk kompilasi LLM Payload.
import { create } from "zustand";
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge as flowAddEdge,
  type Connection,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";
import type {
  ActiveTool,
  AnalysisRunState,
  CanvasBuildProgress,
  CanvasFactoryMeta,
  CanvasFlowEdge,
  CanvasFlowEdgeData,
  CanvasFlowNode,
  CanvasNodeData,
  CanvasNodeKind,
  CanvasShift,
  CanvasSimulationSettings,
  CanvasTemplateId,
  CanvasWorkerProfile,
  OperationalLimits,
  RelationType,
  WorkerUploadState,
} from "@/features/canvas/types/canvas.types";
import { isValidFlowConnection, toFlowGraph } from "@/features/canvas/utils/flowLogic";

interface CanvasSnapshot {
  nodes: CanvasFlowNode[];
  edges: CanvasFlowEdge[];
}

interface CanvasUIState {
  // --- Toolbar mode ---
  activeTool: ActiveTool;
  setActiveTool: (tool: ActiveTool) => void;

  // --- Graph (visual state) ---
  nodes: CanvasFlowNode[];
  edges: CanvasFlowEdge[];
  selectedNodeId: string | null;

  // --- Undo / Redo stack ---
  past: CanvasSnapshot[];
  future: CanvasSnapshot[];

  // --- AI analysis lifecycle ---
  analysis: AnalysisRunState;

  // --- Operational policy limits (sent to the AI/optimization flow) ---
  operationalLimits: OperationalLimits;
  setAllowRecruit: (value: boolean) => void;
  setAllowOvertime: (value: boolean) => void;
  setAllowOutsourcing: (value: boolean) => void;
  setBudgetLimit: (value: number) => void;

  // --- Settings pop-up ---
  settingsOpen: boolean;
  openSettings: () => void;
  closeSettings: () => void;
  applyOperationalLimits: (limits: OperationalLimits) => void;

  // --- Project metadata ---
  projectTitle: string;

  // --- Grup sesi berbasis template (1 templateId = 1 canvasId) ---
  canvasId: string | null;
  templateId: CanvasTemplateId | null;

  // --- Factory, Shift, Simulation & Worker Management ---
  factoryId: string | null;
  factoryMeta: CanvasFactoryMeta;
  shifts: CanvasShift[];
  simulationSettings: CanvasSimulationSettings;
  workerPool: CanvasWorkerProfile[];
  workerAssignments: Record<string, string[]>;
  workerUpload: WorkerUploadState;
  mappingOpen: boolean;
  buildProgress: CanvasBuildProgress;
  setFactoryId: (factoryId: string | null) => void;
  setFactoryMeta: (patch: Partial<CanvasFactoryMeta>) => void;
  setShifts: (shifts: CanvasShift[]) => void;
  upsertShift: (shift: CanvasShift) => void;
  removeShift: (shiftId: string) => void;
  setSimulationSettings: (patch: Partial<CanvasSimulationSettings>) => void;
  setWorkerPool: (workers: CanvasWorkerProfile[]) => void;
  setWorkerUpload: (patch: Partial<WorkerUploadState>) => void;
  assignWorker: (nodeId: string, workerId: string) => void;
  unassignWorker: (nodeId: string, workerId: string) => void;
  setNodeWorkers: (nodeId: string, workerIds: string[]) => void;
  clearWorkerAssignments: () => void;
  autoDistributeWorkers: () => void;
  openMapping: () => void;
  closeMapping: () => void;
  setBuildProgress: (patch: Partial<CanvasBuildProgress>) => void;
  hydrateCanvasMeta: (meta: Partial<CanvasUIState>) => void;

  // --- Actions ---
  snapshot: () => void;
  onNodesChange: (changes: NodeChange<CanvasFlowNode>[]) => void;
  onEdgesChange: (changes: EdgeChange<CanvasFlowEdge>[]) => void;
  onConnect: (connection: Connection) => void;
  addNodeAt: (kind: CanvasNodeKind, position: { x: number; y: number }) => void;
  removeElement: (id: string, isEdge?: boolean) => void;
  updateNodeData: (id: string, patch: Partial<CanvasNodeData> & Record<string, unknown>) => void;
  updateEdgeData: (id: string, patch: Partial<CanvasFlowEdgeData>) => void;
  setSelectedNode: (id: string | null) => void;
  setProjectTitle: (title: string) => void;
  undo: () => void;
  redo: () => void;
  loadTemplate: (initialNodes: CanvasFlowNode[], initialEdges: CanvasFlowEdge[]) => void;
  setSession: (canvasId: string | null, templateId: CanvasTemplateId | null) => void;
  resetCanvas: () => void;
  setAnalysis: (partial: Partial<AnalysisRunState>) => void;
}

let nodeCounter = 0;
const genId = (kind: CanvasNodeKind) => `${kind}-${Date.now().toString(36)}-${++nodeCounter}`;

/** Aturan relasi: process→process (FLOW), worker→process (ASSIGNED_TO), process→output (FLOW). */
export function resolveRelation(
  sourceKind: CanvasNodeKind | undefined,
  targetKind: CanvasNodeKind | undefined
): RelationType | null {
  if (!sourceKind || !targetKind) return null;
  if (sourceKind === "warehouse" && targetKind === "process") return "FLOW";
  if (sourceKind === "process" && targetKind === "process") return "FLOW";
  if (sourceKind === "process" && targetKind === "output") return "FLOW";
  if (sourceKind === "worker" && targetKind === "process") return "ASSIGNED_TO";
  return null;
}

const DEFAULT_FACTORY_META: CanvasFactoryMeta = {
  factoryName: "",
  processType: "serial",
  layoutDescription: "",
  declaredWorkerCount: 0,
};

const DEFAULT_SHIFTS: CanvasShift[] = [
  { shiftId: "shift-01", startTime: "08:00", endTime: "16:00" },
];

const DEFAULT_SIMULATION_SETTINGS: CanvasSimulationSettings = {
  bottleneckFillThreshold: 0.85,
  idleQtyThreshold: 0.05,
  station1SafetyMargin: 0.1,
  warehouseCapacity: 5000,
  warehouseFeedRate: 100,
  shiftStartMinutes: 480,
  breakStartElapsed: 240,
  breakEndElapsed: 300,
  shiftEndElapsed: 480,
  targetOutputUnits: 2500,
  initialBatchSeq: 1,
  analyticalInsightSummary: "",
};

const DEFAULT_WORKER_UPLOAD: WorkerUploadState = {
  status: "idle",
  fileName: null,
  message: null,
  acceptedCount: 0,
  rejectedCount: 0,
};

export const useCanvasUIStore = create<CanvasUIState>((set, get) => ({
  activeTool: "select",
  setActiveTool: (tool) => set({ activeTool: tool }),

  nodes: [],
  edges: [],
  selectedNodeId: null,

  past: [],
  future: [],

  analysis: { status: "idle" },

  projectTitle: "Proyek Pabrik Tanpa Judul",

  canvasId: null,
  templateId: null,

  // --- Factory, Shift, Simulation & Worker Management State ---
  factoryId: null,
  factoryMeta: { ...DEFAULT_FACTORY_META },
  shifts: [...DEFAULT_SHIFTS],
  simulationSettings: { ...DEFAULT_SIMULATION_SETTINGS },
  workerPool: [],
  workerAssignments: {},
  workerUpload: { ...DEFAULT_WORKER_UPLOAD },
  mappingOpen: false,
  buildProgress: { stage: "factory", status: "pending", message: null },

  setFactoryId: (factoryId) => set({ factoryId }),
  setFactoryMeta: (patch) =>
    set((s) => ({ factoryMeta: { ...s.factoryMeta, ...patch } })),
  setShifts: (shifts) => set({ shifts }),
  upsertShift: (shift) =>
    set((s) => {
      const exists = s.shifts.some((item) => item.shiftId === shift.shiftId);
      return {
        shifts: exists
          ? s.shifts.map((item) => (item.shiftId === shift.shiftId ? shift : item))
          : [...s.shifts, shift],
      };
    }),
  removeShift: (shiftId) =>
    set((s) => ({ shifts: s.shifts.filter((item) => item.shiftId !== shiftId) })),
  setSimulationSettings: (patch) =>
    set((s) => ({ simulationSettings: { ...s.simulationSettings, ...patch } })),
  setWorkerPool: (workers) => set({ workerPool: workers }),
  setWorkerUpload: (patch) =>
    set((s) => ({ workerUpload: { ...s.workerUpload, ...patch } })),
  assignWorker: (nodeId, workerId) =>
    set((s) => {
      const next: Record<string, string[]> = {};
      for (const [key, ids] of Object.entries(s.workerAssignments)) {
        next[key] = ids.filter((id) => id !== workerId);
      }
      next[nodeId] = [...(next[nodeId] ?? []), workerId];
      return { workerAssignments: next };
    }),
  unassignWorker: (nodeId, workerId) =>
    set((s) => ({
      workerAssignments: {
        ...s.workerAssignments,
        [nodeId]: (s.workerAssignments[nodeId] ?? []).filter((id) => id !== workerId),
      },
    })),
  setNodeWorkers: (nodeId, workerIds) =>
    set((s) => ({ workerAssignments: { ...s.workerAssignments, [nodeId]: workerIds } })),
  clearWorkerAssignments: () => set({ workerAssignments: {} }),
  autoDistributeWorkers: () => {
    const { nodes, workerPool } = get();
    const processIds = nodes.filter((n) => n.data.kind === "process").map((n) => n.id);
    if (processIds.length === 0) return;
    const next: Record<string, string[]> = {};
    for (const id of processIds) {
      next[id] = [];
    }
    workerPool.forEach((worker, index) => {
      const targetId = processIds[index % processIds.length];
      next[targetId] = [...next[targetId], worker.workerId];
    });
    set({ workerAssignments: next });
  },
  openMapping: () => set({ mappingOpen: true }),
  closeMapping: () => set({ mappingOpen: false }),
  setBuildProgress: (patch) =>
    set((s) => ({ buildProgress: { ...s.buildProgress, ...patch } })),
  hydrateCanvasMeta: (meta) =>
    set({
      factoryId: meta.factoryId ?? null,
      factoryMeta: { ...DEFAULT_FACTORY_META, ...(meta.factoryMeta ?? {}) },
      shifts: meta.shifts && meta.shifts.length > 0 ? meta.shifts : [...DEFAULT_SHIFTS],
      simulationSettings: { ...DEFAULT_SIMULATION_SETTINGS, ...(meta.simulationSettings ?? {}) },
      workerPool: meta.workerPool ?? [],
      workerAssignments: meta.workerAssignments ?? {},
      workerUpload: { ...DEFAULT_WORKER_UPLOAD },
    }),

  // --- Canvas Actions ---
  snapshot: () => {
    const { nodes, edges } = get();
    set((s) => ({ past: [...s.past, { nodes, edges }].slice(-50), future: [] }));
  },

  onNodesChange: (changes) => {
    const next = applyNodeChanges(changes, get().nodes);
    set({ nodes: next });
  },

  onEdgesChange: (changes) => {
    const next = applyEdgeChanges(changes, get().edges);
    set({ edges: next });
  },

  onConnect: (connection) => {
    const { nodes, edges, snapshot } = get();
    const source = nodes.find((n) => n.id === connection.source);
    const target = nodes.find((n) => n.id === connection.target);
    const relation = resolveRelation(source?.data.kind, target?.data.kind);
    if (!relation) return; // relasi invalid: tidak menambah edge

    // Aturan alur FLOW: node level sama tidak bisa saling terhubung,
    // dan node tidak bisa flow ke parent/leluhurnya sendiri.
    if (relation === "FLOW") {
      if (
        !connection.source ||
        !connection.target ||
        !isValidFlowConnection(connection.source, connection.target, toFlowGraph(nodes, edges))
      ) {
        return;
      }
    }

    const exists = edges.some(
      (e) =>
        e.source === connection.source &&
        e.target === connection.target &&
        e.data?.relation === relation
    );
    if (exists) return;

    const data: CanvasFlowEdgeData = { relation };
    if (relation === "FLOW") {
      // Default tipe alur konsisten dengan grup fan-out sumber & grup fan-in tujuan.
      const outGroup = edges.filter(
        (e) => e.source === connection.source && e.data?.relation === "FLOW"
      );
      data.flowType =
        outGroup.find((e) => e.data?.flowType)?.data?.flowType ?? "parallel";
      const inGroup = edges.filter(
        (e) => e.target === connection.target && e.data?.relation === "FLOW"
      );
      data.joinType = inGroup.find((e) => e.data?.joinType)?.data?.joinType ?? "and";
    }

    // Inferensi handle saat koneksi dibuat tanpa handle eksplisit (mis. via
    // tool "Hubungkan"): FLOW selalu source-bottom → target-top; ASSIGNED_TO
    // keluar dari sisi pekerja yang menghadap proses (source-left/source-right).
    let sourceHandle = connection.sourceHandle ?? (relation === "FLOW" ? "source-bottom" : null);
    if (!sourceHandle && source && target) {
      sourceHandle = source.position.x < target.position.x ? "source-right" : "source-left";
    }
    const targetHandle = connection.targetHandle ?? "target-top";

    const newEdge = flowAddEdge(
      {
        ...connection,
        type: relation === "FLOW" ? "flow" : "assigned",
        sourceHandle,
        targetHandle,
        data,
      },
      edges
    );
    snapshot();
    set({ edges: newEdge });
  },

  addNodeAt: (kind, position) => {
    const { snapshot } = get();
    const id = genId(kind);
    const nodeType =
      kind === "process"
        ? "fabric"
        : kind === "output"
          ? "output"
          : kind === "warehouse"
            ? "warehouse"
            : "worker";

    const base: CanvasFlowNode = {
      id,
      type: nodeType,
      position,
      data:
        kind === "process"
          ? {
              kind: "process",
              label: "Proses Baru",
              requiredSkills: [],
              targetOutput: 0,
              aiStatus: "idle",
              jobDesk: null,
            }
          : kind === "output"
            ? {
                kind: "output",
                label: "",
                targetOutput: 0,
                totalOutput: 0,
                aiStatus: "idle",
              }
            : kind === "warehouse"
              ? {
                  kind: "warehouse",
                  label: "Gudang Bahan Baku",
                  capacity: 5000,
                  feedRate: 100,
                  materialName: "Bahan Baku",
                  materialUnit: "pcs",
                  aiStatus: "idle",
                }
              : {
                  kind: "worker",
                  label: "",
                  fatigueScore: 0,
                  aiStatus: "idle",
                  worker: {
                    workerId: id,
                    name: "",
                    demographics: {
                      age: 0,
                      gender: "",
                      yearsOfExperience: 0,
                      baselinePhysicalStamina: 0,
                      cognitiveResilience: 0,
                    },
                    shiftContext: { hoursWorkedToday: 0, consecutiveShifts: 0 },
                    skills: [],
                  },
                },
    };
    snapshot();
    set((s) => ({ nodes: [...s.nodes, base], selectedNodeId: id, activeTool: "select" }));
  },
  
  removeElement: (id, isEdge = false) => {
    const { edges, snapshot } = get();
    if (isEdge) {
      snapshot();
      set({ edges: edges.filter((e) => e.id !== id) });
      return;
    }
    snapshot();
    set((s) => ({
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
    }));
  },

  updateNodeData: (id, patch: Partial<CanvasNodeData> & Record<string, unknown>) => {
    const { nodes } = get();
    set({
      nodes: nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, ...patch } as CanvasNodeData } : n
      ),
    });
  },

  updateEdgeData: (id, patch: Partial<CanvasFlowEdgeData>) => {
    const { edges } = get();
    set({
      edges: edges.map((e) =>
        e.id === id ? { ...e, data: { ...e.data, ...patch } as CanvasFlowEdgeData } : e
      ),
    });
  },

  setSelectedNode: (id) => set({ selectedNodeId: id }),

  setProjectTitle: (title) => set({ projectTitle: title }),

  undo: () => {
    const { past, nodes, edges } = get();
    if (past.length === 0) return;
    const prev = past[past.length - 1];
    set({
      past: past.slice(0, -1),
      future: [...get().future, { nodes, edges }],
      nodes: prev.nodes,
      edges: prev.edges,
    });
  },

  redo: () => {
    const { future, nodes, edges } = get();
    if (future.length === 0) return;
    const next = future[future.length - 1];
    set({
      future: future.slice(0, -1),
      past: [...get().past, { nodes, edges }],
      nodes: next.nodes,
      edges: next.edges,
    });
  },

  loadTemplate: (initialNodes, initialEdges) =>
    set({
      nodes: initialNodes,
      edges: initialEdges,
      past: [],
      future: [],
      selectedNodeId: null,
      analysis: { status: "idle" },
    }),

  setSession: (canvasId, templateId) => set({ canvasId, templateId }),

  resetCanvas: () =>
    set({
      nodes: [],
      edges: [],
      past: [],
      future: [],
      selectedNodeId: null,
      factoryId: null,
      workerPool: [],
      workerAssignments: {},
      workerUpload: { ...DEFAULT_WORKER_UPLOAD },
      buildProgress: { stage: "factory", status: "pending", message: null },
    }),

  setAnalysis: (partial) =>
    set((s) => ({ analysis: { ...s.analysis, ...partial } })),

  operationalLimits: {
    allowRecruitNewEmployees: false,
    allowOvertime: false,
    allowOutsourcing: false,
    budgetLimit: 0,
  },
  setAllowRecruit: (value) =>
    set((s) => ({ operationalLimits: { ...s.operationalLimits, allowRecruitNewEmployees: value } })),
  setAllowOvertime: (value) =>
    set((s) => ({ operationalLimits: { ...s.operationalLimits, allowOvertime: value } })),
  setAllowOutsourcing: (value) =>
    set((s) => ({ operationalLimits: { ...s.operationalLimits, allowOutsourcing: value } })),
  setBudgetLimit: (value) =>
    set((s) => ({ operationalLimits: { ...s.operationalLimits, budgetLimit: value } })),

  settingsOpen: false,
  openSettings: () => set({ settingsOpen: true }),
  closeSettings: () => set({ settingsOpen: false }),
  applyOperationalLimits: (limits) => set({ operationalLimits: limits }),
}));