// frontend/src/features/canvas/utils/graphExtractor.ts
// Kompilasi LLM Payload dari Visual State canvas.
// PENTING: fungsi ini MEMBUANG semua data visual (position, zoom, warna, dsb)
// sehingga payload hanya berisi Graph Data murni sesuai kontrak
// src/features/canvas/types/canvas.types.ts (FactoryGraphPayload).
import type {
  CanvasFlowEdge,
  CanvasFlowNode,
  FactoryGraphEdge,
  FactoryGraphPayload,
} from "../types/canvas.types";
import { normalizeFlowTypes } from "./flowLogic";

/**
 * Merangkum nodes + edges React Flow menjadi JSON payload bersih untuk LLM/Backend.
 * Output mengikuti format:
 * {
 *   "factory_graph": {
 *     "nodes": [{ "id", "type", "label", "required_skills" | "skills", "fatigue_score" }],
 *     "edges": [{
 *       "source", "target", "type": "FLOW" | "ASSIGNED_TO",
 *       "flow_type": "serial" | "parallel",   // Fan-Out antar proses
 *       "join_type": "and" | "or"             // Fan-In antar proses
 *     }]
 *   }
 * }
 */
export function buildFactoryGraphPayload(
  nodes: CanvasFlowNode[],
  edges: CanvasFlowEdge[]
): FactoryGraphPayload {
  const payloadNodes = nodes.map((node) => {
    const d = node.data;
    if (d.kind === "process") {
      return {
        id: node.id,
        type: "process" as const,
        label: d.label,
        required_skills: d.requiredSkills,
      };
    }
    if (d.kind === "output") {
      return {
        id: node.id,
        type: "output" as const,
        label: d.label,
        target_output: d.targetOutput,
      };
    }
    return {
      id: node.id,
      type: "worker" as const,
      label: d.label,
      skills: d.worker.skills ?? [],
      fatigue_score: d.fatigueScore,
    };
  });

  // Tipe alur (flow_type/join_type) diisi default via normalizeFlowTypes
  // berdasarkan struktur Fan-Out/Fan-In pada FLOW edges.
  const payloadEdges = normalizeFlowTypes(
    edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      type: (edge.data?.relation ?? "FLOW") as "FLOW" | "ASSIGNED_TO",
      flow_type: edge.data?.relation === "FLOW" ? edge.data?.flowType : undefined,
      join_type: edge.data?.relation === "FLOW" ? edge.data?.joinType : undefined,
    }))
  ) as FactoryGraphEdge[];

  return {
    factory_graph: {
      nodes: payloadNodes,
      edges: payloadEdges,
    },
  };
}

/** Ringkasan cepat untuk UI (jumlah node per tipe & edge per relasi). */
export function summarizeGraph(
  nodes: CanvasFlowNode[],
  edges: CanvasFlowEdge[]
): {
  processCount: number;
  workerCount: number;
  outputCount: number;
  flowCount: number;
  assignedCount: number;
} {
  return {
    processCount: nodes.filter((n) => n.data.kind === "process").length,
    workerCount: nodes.filter((n) => n.data.kind === "worker").length,
    outputCount: nodes.filter((n) => n.data.kind === "output").length,
    flowCount: edges.filter((e) => e.data?.relation === "FLOW").length,
    assignedCount: edges.filter((e) => e.data?.relation === "ASSIGNED_TO").length,
  };
}