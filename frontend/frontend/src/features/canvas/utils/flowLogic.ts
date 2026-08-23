// frontend/src/features/canvas/utils/flowLogic.ts
// Logika alur (flow semantics) antar node proses — bekerja pada Graph Data murni
// (tanpa koordinat visual), sehingga bisa dipakai untuk payload JSON maupun UI.
//
// Semantik eksekusi:
// - Fan-Out (satu input → banyak output):
//   * Serial Split   : node tujuan dijalankan bergantian (Sequence/Queue).
//   * Parallel Split : node tujuan dijalankan secara bersamaan (Fork).
// - Fan-In (banyak input → satu output):
//   * AND-Join       : node tujuan berjalan jika SEMUA node sebelumnya selesai (Wait All).
//   * OR-Join        : node tujuan langsung berjalan setelah SALAH SATU node selesai (Race).
import type {
  CanvasFlowEdge,
  CanvasFlowNode,
  FlowJoinType,
  FlowSplitType,
} from "../types/canvas.types";

export interface FlowGraphNode {
  id: string;
  type: string;
  label?: string;
}

export interface FlowGraphEdge {
  source: string;
  target: string;
  type: string;
  flow_type?: FlowSplitType;
  join_type?: FlowJoinType;
}

export interface FlowGraph {
  nodes: FlowGraphNode[];
  edges: FlowGraphEdge[];
}

/** Konversi Visual State (nodes/edges React Flow) → Graph Data murni. */
export function toFlowGraph(nodes: CanvasFlowNode[], edges: CanvasFlowEdge[]): FlowGraph {
  return {
    nodes: nodes.map((n) => ({ id: n.id, type: n.data.kind, label: n.data.label })),
    edges: edges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.data?.relation ?? "FLOW",
      flow_type: e.data?.relation === "FLOW" ? e.data?.flowType : undefined,
      join_type: e.data?.relation === "FLOW" ? e.data?.joinType : undefined,
    })),
  };
}

function groupBy<T, K extends string>(items: T[], keyFn: (item: T) => K): Map<K, T[]> {
  const map = new Map<K, T[]>();
  for (const item of items) {
    const k = keyFn(item);
    const arr = map.get(k);
    if (arr) arr.push(item);
    else map.set(k, [item]);
  }
  return map;
}

const edgeKey = (e: FlowGraphEdge) => `${e.source}\u0000${e.target}\u0000${e.type}`;

/**
 * Mengisi tipe alur default pada FLOW edges (non-mutating):
 * - Fan-Out (1 sumber → N tujuan): "parallel" (fork) secara default; jika salah satu
 *   edge dalam grup sudah ditandai "serial", seluruh grup menjadi "serial" (konsisten).
 * - Tujuan tunggal: "serial" (antrian sekuensial).
 * - Fan-In (N sumber → 1 tujuan): "and" (tunggu semua) secara default; jika salah satu
 *   edge dalam grup sudah ditandai "or", seluruh grup menjadi "or" (konsisten).
 */
export function normalizeFlowTypes(edges: FlowGraphEdge[]): FlowGraphEdge[] {
  const flowEdges = edges.filter((e) => e.type === "FLOW");
  const bySource = groupBy(flowEdges, (e) => e.source);
  const byTarget = groupBy(flowEdges, (e) => e.target);

  const patch = new Map<string, { flow_type?: FlowSplitType; join_type?: FlowJoinType }>();

  for (const group of bySource.values()) {
    const explicit = group.find((e) => e.flow_type === "serial" || e.flow_type === "parallel");
    const flowType: FlowSplitType = explicit?.flow_type ?? (group.length > 1 ? "parallel" : "serial");
    for (const e of group) {
      patch.set(edgeKey(e), { ...(patch.get(edgeKey(e)) ?? {}), flow_type: flowType });
    }
  }

  for (const group of byTarget.values()) {
    const explicit = group.find((e) => e.join_type === "and" || e.join_type === "or");
    const joinType: FlowJoinType = explicit?.join_type ?? "and";
    for (const e of group) {
      patch.set(edgeKey(e), { ...(patch.get(edgeKey(e)) ?? {}), join_type: joinType });
    }
  }

  return edges.map((e) => (e.type === "FLOW" ? { ...e, ...(patch.get(edgeKey(e)) ?? {}) } : e));
}

/**
 * Menghitung jadwal eksekusi proses berdasarkan semantik alur.
 * Return: array "round" (tahap); node dalam round yang sama dijalankan bersamaan,
 * node di round berikutnya menunggu dependensinya selesai.
 * - Parallel Split: semua tujuan masuk round yang sama (bersamaan).
 * - Serial Split  : tujuan masuk round berurutan (bergantian).
 * - AND-Join      : node baru siap jika SEMUA sumber selesai.
 * - OR-Join       : node siap setelah SALAH SATU sumber selesai.
 */
export function computeExecutionRounds(graph: FlowGraph): string[][] {
  const processIds = graph.nodes.filter((n) => n.type === "process").map((n) => n.id);
  const flowEdges = normalizeFlowTypes(graph.edges.filter((e) => e.type === "FLOW"));
  const inByTarget = groupBy(flowEdges, (e) => e.target);
  const outBySource = groupBy(flowEdges, (e) => e.source);

  const started = new Set<string>();
  const completed = new Set<string>();
  const rounds: string[][] = [];

  while (started.size < processIds.length) {
    const starting = processIds.filter(
      (id) => !started.has(id) && canStart(id, inByTarget, outBySource, completed)
    );
    if (starting.length === 0) break; // guard: siklus / tidak ada progres
    rounds.push(starting);
    for (const id of starting) {
      started.add(id);
      completed.add(id);
    }
  }

  return rounds;
}

function canStart(
  id: string,
  inByTarget: Map<string, FlowGraphEdge[]>,
  outBySource: Map<string, FlowGraphEdge[]>,
  completed: Set<string>
): boolean {
  const ins = inByTarget.get(id) ?? [];
  if (ins.length === 0) return true;

  // Fan-In: AND (semua selesai) atau OR (salah satu selesai).
  const joinType = ins[0].join_type ?? "and";
  const doneSources = ins.filter((e) => completed.has(e.source)).length;
  if (joinType === "or" ? doneSources === 0 : doneSources < ins.length) return false;

  // Serial Split: tujuan ke-i menunggu tujuan ke-(i-1) pada grup yang sama.
  for (const inEdge of ins) {
    const group = outBySource.get(inEdge.source) ?? [];
    if (group.length < 2) continue;
    if ((group[0].flow_type ?? "parallel") !== "serial") continue;
    const idx = group.findIndex((e) => e.target === id);
    if (idx > 0 && !completed.has(group[idx - 1].target)) return false;
  }

  return true;
}

/**
 * Level node proses = panjang jalur terpanjang dari root (longest-path),
 * dihitung per komponen FLOW. Leluhur selalu berada di level yang lebih kecil,
 * sehingga level yang sama berarti posisi "sejajar" (paralel) dalam alur.
 */
export function computeNodeLevels(graph: FlowGraph): Map<string, number> {
  const flowEdges = graph.edges.filter((e) => e.type === "FLOW");
  const inByTarget = groupBy(flowEdges, (e) => e.target);
  const memo = new Map<string, number>();
  const visiting = new Set<string>();

  const level = (id: string): number => {
    const cached = memo.get(id);
    if (cached !== undefined) return cached;
    if (visiting.has(id)) return 0; // guard siklus
    visiting.add(id);
    const parents = (inByTarget.get(id) ?? []).map((e) => e.source);
    let lv = 0;
    for (const p of parents) lv = Math.max(lv, level(p) + 1);
    visiting.delete(id);
    memo.set(id, lv);
    return lv;
  };

  for (const n of graph.nodes) {
    if (n.type === "process") level(n.id);
  }
  return memo;
}

/** Komponen terhubung (undirected) antar node proses via FLOW edges. */
function computeComponents(flowEdges: FlowGraphEdge[]): Map<string, string> {
  const adj = new Map<string, Set<string>>();
  for (const e of flowEdges) {
    if (!adj.has(e.source)) adj.set(e.source, new Set());
    if (!adj.has(e.target)) adj.set(e.target, new Set());
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  }

  const comp = new Map<string, string>();
  let root = 0;
  for (const [id] of adj) {
    if (comp.has(id)) continue;
    const r = `c${root++}`;
    const stack = [id];
    comp.set(id, r);
    while (stack.length) {
      const cur = stack.pop()!;
      for (const nb of adj.get(cur) ?? []) {
        if (!comp.has(nb)) {
          comp.set(nb, r);
          stack.push(nb);
        }
      }
    }
  }
  return comp;
}

/** Apakah `ancestorId` merupakan leluhur (parent/nenek moyang) dari `fromId`? */
function isAncestor(ancestorId: string, fromId: string, flowEdges: FlowGraphEdge[]): boolean {
  const inByTarget = groupBy(flowEdges, (e) => e.target);
  const stack = [fromId];
  const seen = new Set<string>();
  while (stack.length) {
    const cur = stack.pop()!;
    if (cur === ancestorId) return true;
    if (seen.has(cur)) continue;
    seen.add(cur);
    for (const e of inByTarget.get(cur) ?? []) stack.push(e.source);
  }
  return false;
}

/**
 * Validasi koneksi FLOW antar node proses:
 * 1. Node pada level yang sama (satu komponen) tidak bisa saling terhubung
 *    (hanya paralel "menyamping" — bukan flow maju/mundur).
 * 2. Node tidak bisa flow ke parent/leluhurnya sendiri (mencegah siklus ke atas).
 * Kembalian `true` juga untuk koneksi yang melibatkan non-proses (diputuskan
 * oleh aturan relasi lain, mis. worker → process).
 */
export function isValidFlowConnection(
  sourceId: string,
  targetId: string,
  graph: FlowGraph
): boolean {
  if (!sourceId || !targetId || sourceId === targetId) return false;

  const flowEdges = graph.edges.filter((e) => e.type === "FLOW");
  const levels = computeNodeLevels(graph);
  if (!levels.has(sourceId) || !levels.has(targetId)) return true;

  // Aturan 1: level sama dalam komponen yang sama → tidak valid.
  const components = computeComponents(flowEdges);
  const srcComp = components.get(sourceId);
  if (
    srcComp !== undefined &&
    srcComp === components.get(targetId) &&
    levels.get(sourceId) === levels.get(targetId)
  ) {
    return false;
  }

  // Aturan 2: target merupakan leluhur sumber → tidak valid.
  if (isAncestor(targetId, sourceId, flowEdges)) return false;

  return true;
}

/** Deskripsi semantik alur (Fan-Out/Fan-In) untuk dibaca manusia/LLM. */
export function describeFlowSemantics(graph: FlowGraph): string[] {
  const labels = new Map(graph.nodes.map((n) => [n.id, n.label ?? n.id]));
  const name = (id: string) => labels.get(id) ?? id;

  const flowEdges = normalizeFlowTypes(graph.edges.filter((e) => e.type === "FLOW"));
  const bySource = groupBy(flowEdges, (e) => e.source);
  const byTarget = groupBy(flowEdges, (e) => e.target);

  const lines: string[] = [];

  for (const [source, group] of bySource) {
    if (group.length < 2) continue;
    const type = group[0].flow_type ?? "parallel";
    lines.push(
      `Fan-Out ${type === "serial" ? "Serial Split (tujuan bergantian)" : "Parallel Split (tujuan bersamaan)"}: ${name(source)} → ${group
        .map((e) => name(e.target))
        .join(", ")}`
    );
  }

  for (const [target, group] of byTarget) {
    if (group.length < 2) continue;
    const type = group[0].join_type ?? "and";
    lines.push(
      `Fan-In ${type === "and" ? "AND-Join (tunggu semua selesai)" : "OR-Join (jalankan saat pertama selesai)"}: ${group
        .map((e) => name(e.source))
        .join(", ")} → ${name(target)}`
    );
  }

  return lines;
}