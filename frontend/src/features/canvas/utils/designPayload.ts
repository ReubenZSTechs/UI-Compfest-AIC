import type {
  CanvasFactoryMeta,
  CanvasFlowEdge,
  CanvasFlowNode,
  CanvasProcessData,
  CanvasShift,
  CanvasSimulationSettings,
  CanvasWorkerData,
} from "../types/canvas.types";
import { computeExecutionRounds, toFlowGraph } from "./flowLogic";
import { DEFAULT_SHIFT_ID, resolveProcessSpecs } from "./processSpecs";

export interface DesignPayloadInput {
  nodes: CanvasFlowNode[];
  edges: CanvasFlowEdge[];
  factoryMeta: CanvasFactoryMeta;
  shifts: CanvasShift[];
  settings: CanvasSimulationSettings;
  workerAssignments: Record<string, string[]>;
}

export interface DesignValidationIssue {
  nodeId: string | null;
  message: string;
}

function isProcessNode(node: CanvasFlowNode): boolean {
  return node.data.kind === "process";
}

function orderProcessNodes(nodes: CanvasFlowNode[], edges: CanvasFlowEdge[]): CanvasFlowNode[] {
  const processNodes = nodes.filter(isProcessNode);
  const rounds = computeExecutionRounds(toFlowGraph(nodes, edges));
  const orderedIds = rounds.flat();
  const byId = new Map(processNodes.map((node) => [node.id, node]));
  const ordered: CanvasFlowNode[] = [];

  for (const id of orderedIds) {
    const node = byId.get(id);
    if (node) {
      ordered.push(node);
      byId.delete(id);
    }
  }
  return [...ordered, ...byId.values()];
}

function collectEdgeWorkerIds(
  nodeId: string,
  nodes: CanvasFlowNode[],
  edges: CanvasFlowEdge[]
): string[] {
  const workerNodeIds = edges
    .filter((edge) => edge.target === nodeId && edge.data?.relation === "ASSIGNED_TO")
    .map((edge) => edge.source);

  return workerNodeIds
    .map((id) => nodes.find((node) => node.id === id))
    .filter((node): node is CanvasFlowNode => Boolean(node) && node!.data.kind === "worker")
    .map((node) => (node.data as CanvasWorkerData).worker.workerId)
    .filter(Boolean);
}

function deriveProcessType(
  processEdges: Array<{ fromStageId: string; toStageId: string }>
): CanvasFactoryMeta["processType"] {
  const outDegree = new Map<string, number>();
  const inDegree = new Map<string, number>();

  for (const edge of processEdges) {
    outDegree.set(edge.fromStageId, (outDegree.get(edge.fromStageId) ?? 0) + 1);
    inDegree.set(edge.toStageId, (inDegree.get(edge.toStageId) ?? 0) + 1);
  }

  const hasSplit = [...outDegree.values()].some((count) => count > 1);
  const hasJoin = [...inDegree.values()].some((count) => count > 1);

  if (hasSplit && hasJoin) return "hybrid";
  if (hasSplit || hasJoin) return "parallel";
  return "serial";
}

export function validateDesignInput(input: DesignPayloadInput): DesignValidationIssue[] {
  const issues: DesignValidationIssue[] = [];
  const processNodes = input.nodes.filter(isProcessNode);

  if (processNodes.length === 0) {
    issues.push({ nodeId: null, message: "Kanvas belum memiliki node proses." });
  }

  const shiftIds = new Set(input.shifts.map((shift) => shift.shiftId));

  processNodes.forEach((node, index) => {
    const data = node.data as CanvasProcessData;
    const { stage, job } = resolveProcessSpecs(node, index);

    if (!data.label.trim()) {
      issues.push({ nodeId: node.id, message: "Nama proses masih kosong." });
    }
    if (stage.cycleTimeSeconds <= 0) {
      issues.push({ nodeId: node.id, message: "Cycle time harus lebih besar dari 0 detik." });
    }
    if (!shiftIds.has(job.shiftId)) {
      issues.push({
        nodeId: node.id,
        message: `Shift '${job.shiftId}' tidak terdaftar pada pengaturan shift.`,
      });
    }
  });

  return issues;
}

export function buildSimulationDesignPayload(input: DesignPayloadInput) {
  const { nodes, edges, factoryMeta, shifts, settings, workerAssignments } = input;
  const orderedNodes = orderProcessNodes(nodes, edges);
  const specsByNodeId = new Map(
    orderedNodes.map((node, index) => [node.id, resolveProcessSpecs(node, index)])
  );

  const stageIdByNodeId = new Map(
    orderedNodes.map((node) => [node.id, specsByNodeId.get(node.id)!.stage.stageId])
  );

  const processEdges = edges
    .filter((edge) => edge.data?.relation === "FLOW")
    .map((edge) => ({
      fromStageId: stageIdByNodeId.get(edge.source),
      toStageId: stageIdByNodeId.get(edge.target),
    }))
    .filter(
      (edge): edge is { fromStageId: string; toStageId: string } =>
        Boolean(edge.fromStageId) && Boolean(edge.toStageId)
    );

  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();

  for (const edge of processEdges) {
    outgoing.set(edge.fromStageId, [...(outgoing.get(edge.fromStageId) ?? []), edge.toStageId]);
    incoming.set(edge.toStageId, [...(incoming.get(edge.toStageId) ?? []), edge.fromStageId]);
  }

  const effectiveShifts =
    shifts.length > 0 ? shifts : [{ shiftId: DEFAULT_SHIFT_ID, startTime: "08:00", endTime: "16:00" }];

  const assets = orderedNodes.map((node) => {
    const { asset } = specsByNodeId.get(node.id)!;
    return {
      assetId: asset.assetId,
      assetName: asset.assetName,
      category: asset.category,
      unitsAvailable: asset.unitsAvailable,
      capacityPerUnit: asset.capacityPerUnit,
      totalCapacity: asset.totalCapacity,
      automationLevel: asset.automationLevel,
      isAutomated: asset.isAutomated,
      operationalCostPerHour: asset.operationalCostPerHour,
      currency: asset.currency,
      environmentalFactors: asset.environmentalFactors,
    };
  });

  const processStages = orderedNodes.map((node) => {
    const { stage, asset } = specsByNodeId.get(node.id)!;
    const nextStages = outgoing.get(stage.stageId) ?? [];

    return {
      stageId: stage.stageId,
      stageName: (node.data as CanvasProcessData).label,
      lane: stage.lane,
      nextStageId: nextStages[0] ?? null,
      isTerminal: nextStages.length === 0,
      assetId: asset.assetId,
      operatorTask: stage.operatorTask,
      materialInput: stage.materialInput,
      materialOutput: stage.materialOutput,
      materialPerBatch: stage.materialPerBatch,
      flowType: stage.flowType,
      cycleTimeSeconds: stage.cycleTimeSeconds,
      throughput: stage.throughput,
      throughputPerHour: stage.throughputPerHour,
      automationLevel: stage.automationLevel,
      qcRequirement: stage.qcRequirement,
    };
  });

  const jobDesks = orderedNodes.map((node) => {
    const { job, stage, asset } = specsByNodeId.get(node.id)!;
    const mapped = workerAssignments[node.id] ?? [];
    const fromEdges = collectEdgeWorkerIds(node.id, nodes, edges);
    const assignedWorkerIds = [...new Set([...mapped, ...fromEdges])];

    return {
      jobId: job.jobId,
      jobTitle: job.jobTitle,
      stageId: stage.stageId,
      assignedAssetId: asset.assetId,
      assignedWorkerIds,
      shiftId: effectiveShifts.some((shift) => shift.shiftId === job.shiftId)
        ? job.shiftId
        : effectiveShifts[0].shiftId,
      headcount: Math.max(1, job.headcount),
      demands: job.demands,
      qcRequirement: job.qcRequirement,
    };
  });

  const stations = orderedNodes.map((node, index) => {
    const { station, stage } = specsByNodeId.get(node.id)!;
    return {
      ordinal: index + 1,
      stageId: stage.stageId,
      stepName: (node.data as CanvasProcessData).label,
      materialName: station.materialName,
      materialUnit: station.materialUnit,
      stepCostBase: station.stepCostBase,
      capacity: Math.max(1, station.capacity),
      batchIn: Math.max(1, station.batchIn),
      batchOut: Math.max(1, station.batchOut),
      cycleTicks: Math.max(1, station.cycleTicks),
    };
  });

  const stageIds = processStages.map((stage) => stage.stageId);
  const entryStages = stageIds.filter((id) => (incoming.get(id) ?? []).length === 0);
  const terminalStages = stageIds.filter((id) => (outgoing.get(id) ?? []).length === 0);
  const lanes = [...new Set(processStages.map((stage) => stage.lane))];

  const outputNode = nodes.find((node) => node.data.kind === "output");
  const targetOutputUnits =
    outputNode && outputNode.data.kind === "output" && outputNode.data.targetOutput > 0
      ? outputNode.data.targetOutput
      : settings.targetOutputUnits;

  return {
    factoryInfo: {
      processType: deriveProcessType(processEdges),
      layoutDescription: factoryMeta.layoutDescription,
      workflowSequence: stageIds,
      processEdges,
      entryStages,
      terminalStages,
      lanes,
    },
    assets,
    processStages,
    shifts: effectiveShifts,
    jobDesks,
    stations,
    settings: {
      bottleneckFillThreshold: settings.bottleneckFillThreshold,
      idleQtyThreshold: settings.idleQtyThreshold,
      station1SafetyMargin: settings.station1SafetyMargin,
      warehouseCapacity: settings.warehouseCapacity,
      warehouseFeedRate: settings.warehouseFeedRate,
      shiftStartMinutes: settings.shiftStartMinutes,
      breakStartElapsed: settings.breakStartElapsed,
      breakEndElapsed: settings.breakEndElapsed,
      shiftEndElapsed: settings.shiftEndElapsed,
      analyticalInsightSummary: settings.analyticalInsightSummary,
      targetOutputUnits,
      initialBatchSeq: settings.initialBatchSeq,
    },
    workerMultipliers: [],
    seedAssignments: [],
    pruneMissing: true,
  };
}

export type SimulationDesignPayload = ReturnType<typeof buildSimulationDesignPayload>;