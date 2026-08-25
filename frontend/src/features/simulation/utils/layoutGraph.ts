import type { StepBreakdown } from '../types/simulation.types';

export interface LayoutNode {
  step: StepBreakdown;
  depth: number;
  lane: number;
}

export interface LayoutColumn {
  depth: number;
  nodes: LayoutNode[];
}

export interface FlowLayout {
  columns: LayoutColumn[];
  depthByStepId: Record<string, number>;
  laneByStepId: Record<string, number>;
  maxLaneCount: number;
}

function buildAdjacency(steps: StepBreakdown[]) {
  const successors = new Map<string, string[]>();
  const predecessors = new Map<string, string[]>();
  const known = new Set(steps.map((step) => step.step_id));

  for (const step of steps) {
    successors.set(step.step_id, []);
    predecessors.set(step.step_id, []);
  }

  for (const step of steps) {
    for (const target of step.next_step_ids ?? []) {
      if (!known.has(target)) continue;
      successors.get(step.step_id)!.push(target);
      predecessors.get(target)!.push(step.step_id);
    }
  }

  return { successors, predecessors };
}

function computeDepths(
  steps: StepBreakdown[],
  successors: Map<string, string[]>,
  predecessors: Map<string, string[]>
): Record<string, number> {
  const indegree = new Map<string, number>();
  const depth: Record<string, number> = {};

  for (const step of steps) {
    indegree.set(step.step_id, predecessors.get(step.step_id)!.length);
    depth[step.step_id] = 0;
  }

  const queue = steps
    .filter((step) => indegree.get(step.step_id) === 0)
    .map((step) => step.step_id);

  let cursor = 0;
  const visited = new Set<string>(queue);

  while (cursor < queue.length) {
    const current = queue[cursor];
    cursor += 1;

    for (const target of successors.get(current) ?? []) {
      depth[target] = Math.max(depth[target], depth[current] + 1);
      indegree.set(target, (indegree.get(target) ?? 1) - 1);

      if (indegree.get(target) === 0 && !visited.has(target)) {
        visited.add(target);
        queue.push(target);
      }
    }
  }

  // Cycle guard: apapun yang tidak terjangkau topological sort tetap
  // ditempatkan setelah predecessor terdalamnya agar tidak hilang dari layout.
  for (const step of steps) {
    if (visited.has(step.step_id)) continue;
    const parents = predecessors.get(step.step_id) ?? [];
    const deepestParent = parents.reduce((max, id) => Math.max(max, depth[id] ?? 0), -1);
    depth[step.step_id] = deepestParent + 1;
  }

  return depth;
}

function assignLanes(
  columns: Map<number, StepBreakdown[]>,
  predecessors: Map<string, string[]>,
  laneByStepId: Record<string, number>
): void {
  const depths = [...columns.keys()].sort((a, b) => a - b);

  for (const depth of depths) {
    const bucket = columns.get(depth)!;

    const scored = bucket.map((step) => {
      const parents = predecessors.get(step.step_id) ?? [];
      const parentLanes = parents
        .map((id) => laneByStepId[id])
        .filter((lane) => lane !== undefined);

      const anchor =
        parentLanes.length > 0
          ? parentLanes.reduce((sum, lane) => sum + lane, 0) / parentLanes.length
          : Number.MAX_SAFE_INTEGER;

      return { step, anchor };
    });

    scored.sort((a, b) => {
      if (a.anchor !== b.anchor) return a.anchor - b.anchor;
      return a.step.step_id.localeCompare(b.step.step_id);
    });

    scored.forEach((entry, index) => {
      laneByStepId[entry.step.step_id] = index;
    });
  }
}

export function buildFlowLayout(steps: StepBreakdown[]): FlowLayout {
  if (steps.length === 0) {
    return { columns: [], depthByStepId: {}, laneByStepId: {}, maxLaneCount: 0 };
  }

  const { successors, predecessors } = buildAdjacency(steps);
  const depthByStepId = computeDepths(steps, successors, predecessors);

  const grouped = new Map<number, StepBreakdown[]>();
  for (const step of steps) {
    const depth = depthByStepId[step.step_id];
    grouped.set(depth, [...(grouped.get(depth) ?? []), step]);
  }

  const laneByStepId: Record<string, number> = {};
  assignLanes(grouped, predecessors, laneByStepId);

  const columns: LayoutColumn[] = [...grouped.keys()]
    .sort((a, b) => a - b)
    .map((depth) => ({
      depth,
      nodes: grouped
        .get(depth)!
        .map((step) => ({
          step,
          depth,
          lane: laneByStepId[step.step_id],
        }))
        .sort((a, b) => a.lane - b.lane),
    }));

  const maxLaneCount = columns.reduce((max, column) => Math.max(max, column.nodes.length), 0);

  return { columns, depthByStepId, laneByStepId, maxLaneCount };
}