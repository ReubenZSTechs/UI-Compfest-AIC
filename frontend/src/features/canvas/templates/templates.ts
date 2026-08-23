// frontend/src/features/canvas/templates/templates.ts
// Template awal canvas: Kanvas Kosong, Alur Seri, Alur Paralel.
// Hanya mengisi VISUAL STATE (nodes/edges) — belum ada interaksi API.
import type { CanvasFlowEdge, CanvasFlowNode } from "../types/canvas.types";
import type { CanvasTemplateId, FlowJoinType, FlowSplitType } from "../types/canvas.types";

const GAP_Y = 240;
const START_Y = 240;
const COL_X = 460;
const WORKER_OFFSET_X = 340;
const BRANCH_GAP_X = 560;

let counter = 0;
const nid = (kind: "process" | "worker" | "output") => `${kind}-tpl-${++counter}`;

function processNode(
  label: string,
  requiredSkills: string[],
  x: number,
  y: number
): CanvasFlowNode {
  return {
    id: nid("process"),
    type: "fabric",
    position: { x, y },
    data: {
      kind: "process",
      label,
      requiredSkills,
      targetOutput: 250,
      aiStatus: "idle",
      jobDesk: null,
    },
  };
}

function workerNode(name: string, skills: string[], fatigueScore: number, x: number, y: number): CanvasFlowNode {
  return {
    id: nid("worker"),
    type: "worker",
    position: { x, y },
    data: {
      kind: "worker",
      label: name,
      fatigueScore,
      aiStatus: "idle",
      worker: {
        workerId: `wrk-${Date.now().toString(36)}-${++counter}`,
        name,
        demographics: {
          age: 28,
          gender: "-",
          yearsOfExperience: 3,
          baselinePhysicalStamina: 0.68,
          cognitiveResilience: 0.72,
        },
        shiftContext: { hoursWorkedToday: 5.5, consecutiveShifts: 2 },
        skills,
      },
    },
  };
}

function outputNode(label: string, targetOutput: number, x: number, y: number): CanvasFlowNode {
  return {
    id: nid("output"),
    type: "output",
    position: { x, y },
    data: {
      kind: "output",
      label,
      targetOutput,
      totalOutput: 0,
      aiStatus: "idle",
    },
  };
}

const flowEdge = (source: string, target: string, flowType: FlowSplitType = "serial"): CanvasFlowEdge => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: "flow",
  sourceHandle: "source-bottom",
  targetHandle: "target-top",
  data: { relation: "FLOW", flowType },
});

const joinEdge = (source: string, target: string, joinType: FlowJoinType = "and"): CanvasFlowEdge => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: "flow",
  sourceHandle: "source-bottom",
  targetHandle: "target-top",
  data: { relation: "FLOW", joinType },
});

const assignedEdge = (source: string, target: string): CanvasFlowEdge => ({
  id: `e-${source}-${target}`,
  source,
  target,
  type: "assigned",
  // Template menempatkan pekerja di kanan proses, jadi garis keluar dari sisi kiri
  // pekerja (source-left) menuju target atas proses (target-top).
  sourceHandle: "source-left",
  targetHandle: "target-top",
  data: { relation: "ASSIGNED_TO" },
});

function serialTemplate(): { nodes: CanvasFlowNode[]; edges: CanvasFlowEdge[] } {
  const nodes: CanvasFlowNode[] = [];
  const edges: CanvasFlowEdge[] = [];

  const steps: Array<[string, string[]]> = [
    ["Pemotongan Bahan", ["Cutting"]],
    ["Stasiun Jahit A", ["Sewing"]],
    ["Perakitan Produk", ["Assembly"]],
    ["QC & Pengemasan", ["Quality Control", "Packaging"]],
  ];

  steps.forEach(([label, skills], i) => {
    nodes.push(processNode(label, skills, COL_X, START_Y + i * GAP_Y));
    if (i > 0) {
      edges.push(flowEdge(nodes[i - 1].id, nodes[i].id));
    }
  });

  const workerY = START_Y + GAP_Y;
  nodes.push(workerNode("Arif Nugroho", ["Sewing", "Cutting"], 15, COL_X + WORKER_OFFSET_X, workerY));
  nodes.push(workerNode("Bambang Sutrisno", ["Assembly", "Quality Control"], 32, COL_X + WORKER_OFFSET_X, workerY + GAP_Y));

  edges.push(assignedEdge(nodes[3].id, nodes[1].id)); // worker -> process jahit
  edges.push(assignedEdge(nodes[4].id, nodes[2].id)); // worker -> process perakitan

  // Node output: finished goods storage (ujung alur produksi).
  const out = outputNode("Finished Goods Storage", 250, COL_X, START_Y + 4 * GAP_Y);
  nodes.push(out);
  edges.push(flowEdge(nodes[3].id, out.id)); // QC & Pengemasan -> Output

  return { nodes, edges };
}

function parallelTemplate(): { nodes: CanvasFlowNode[]; edges: CanvasFlowEdge[] } {
  const nodes: CanvasFlowNode[] = [];
  const edges: CanvasFlowEdge[] = [];

  const start = processNode("Persiapan Bahan", ["Cutting"], COL_X, START_Y);
  const branchA = processNode("Lini Jahit Paralel", ["Sewing"], COL_X, START_Y + GAP_Y);
  const branchB = processNode("Lini Potong Paralel", ["Cutting", "Marking"], COL_X + BRANCH_GAP_X, START_Y + GAP_Y);
  const merge = processNode("Penyatuan & Finishing", ["Assembly", "Quality Control"], COL_X + BRANCH_GAP_X / 2 - 120, START_Y + 2 * GAP_Y);

  nodes.push(start, branchA, branchB, merge);
  edges.push(
    flowEdge(start.id, branchA.id, "parallel"),
    flowEdge(start.id, branchB.id, "parallel"),
    joinEdge(branchA.id, merge.id, "and"),
    joinEdge(branchB.id, merge.id, "and")
  );

  const w1 = workerNode("Citra Lestari", ["Sewing"], 22, COL_X + WORKER_OFFSET_X, START_Y + GAP_Y);
  const w2 = workerNode("Dedi Firmansyah", ["Cutting", "Marking"], 41, COL_X + BRANCH_GAP_X + WORKER_OFFSET_X, START_Y + GAP_Y);
  nodes.push(w1, w2);
  edges.push(assignedEdge(w1.id, branchA.id), assignedEdge(w2.id, branchB.id));

  // Node output: finished goods storage (ujung alur paralel).
  const out = outputNode("Finished Goods Storage", 250, COL_X + BRANCH_GAP_X / 2 - 120, START_Y + 3 * GAP_Y);
  nodes.push(out);
  edges.push(flowEdge(merge.id, out.id));

  return { nodes, edges };
}

function blankTemplate(): { nodes: CanvasFlowNode[]; edges: CanvasFlowEdge[] } {
  return { nodes: [], edges: [] };
}

export const CANVAS_TEMPLATES: Record<CanvasTemplateId, () => { nodes: CanvasFlowNode[]; edges: CanvasFlowEdge[] }> = {
  blank: blankTemplate,
  serial: serialTemplate,
  parallel: parallelTemplate,
};

export const TEMPLATE_META: Record<CanvasTemplateId, { title: string; description: string }> = {
  blank: {
    title: "Kanvas Kosong",
    description: "Mulai dari nol. Tambahkan node proses & pekerja sesukamu.",
  },
  serial: {
    title: "Alur Seri",
    description: "Proses berurutan A → B → C dengan penugasan pekerja.",
  },
  parallel: {
    title: "Alur Paralel",
    description: "Satu sumber bercabang ke beberapa lini, lalu menyatu lagi.",
  },
};