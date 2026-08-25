import type {
  CanvasAssetSpec,
  CanvasFlowNode,
  CanvasJobSpec,
  CanvasProcessData,
  CanvasQuantity,
  CanvasStageSpec,
  CanvasStationSpec,
} from "../types/canvas.types";

export const DEFAULT_SHIFT_ID = "shift-01";

export function sanitizeId(raw: string, fallback: string): string {
  const cleaned = raw
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned.length > 0 ? cleaned : fallback;
}

export function emptyQuantity(): CanvasQuantity {
  return { value: null, unit: null, unitClass: null, basis: null };
}

function slugFromNode(node: CanvasFlowNode, index: number, prefix: string): string {
  const data = node.data as CanvasProcessData;
  const base = data.label ? sanitizeId(data.label, `${prefix}_${index + 1}`) : `${prefix}_${index + 1}`;
  return `${prefix}_${String(index + 1).padStart(2, "0")}_${base}`.slice(0, 60);
}

export function resolveStageSpec(node: CanvasFlowNode, index: number): CanvasStageSpec {
  const data = node.data as CanvasProcessData;
  const existing = data.stage;
  const target = data.targetOutput > 0 ? data.targetOutput : 100;

  return {
    stageId: existing?.stageId ?? slugFromNode(node, index, "stage"),
    lane: existing?.lane ?? "main",
    operatorTask: existing?.operatorTask ?? data.label,
    flowType: existing?.flowType ?? "batch",
    cycleTimeSeconds: existing?.cycleTimeSeconds ?? 60,
    throughput: existing?.throughput ?? {
      value: target,
      unit: "pcs",
      unitClass: "count",
      basis: "per_hour",
    },
    throughputPerHour: existing?.throughputPerHour ?? target,
    automationLevel: existing?.automationLevel ?? "manual",
    qcRequirement: existing?.qcRequirement ?? "visual_inspection",
    materialInput: existing?.materialInput ?? [],
    materialOutput: existing?.materialOutput ?? [],
    materialPerBatch: existing?.materialPerBatch ?? [],
  };
}

export function resolveAssetSpec(node: CanvasFlowNode, index: number): CanvasAssetSpec {
  const data = node.data as CanvasProcessData;
  const existing = data.asset;
  const target = data.targetOutput > 0 ? data.targetOutput : 100;

  return {
    assetId: existing?.assetId ?? slugFromNode(node, index, "asset"),
    assetName: existing?.assetName ?? `${data.label} Station`,
    category: existing?.category ?? "manual_station",
    unitsAvailable: existing?.unitsAvailable ?? 1,
    capacityPerUnit: existing?.capacityPerUnit ?? {
      value: target,
      unit: "pcs",
      unitClass: "count",
      basis: "per_hour",
    },
    totalCapacity: existing?.totalCapacity ?? {
      value: target * (existing?.unitsAvailable ?? 1),
      unit: "pcs",
      unitClass: "count",
      basis: "per_hour",
    },
    automationLevel: existing?.automationLevel ?? "manual",
    isAutomated: existing?.isAutomated ?? false,
    operationalCostPerHour: existing?.operationalCostPerHour ?? 0,
    currency: existing?.currency ?? "IDR",
    environmentalFactors: existing?.environmentalFactors ?? {
      powerConsumptionWatt: null,
      noiseLevelDb: null,
      vibrationHazardLevel: "low",
      physicalStrainIndex: 0,
    },
  };
}

export function resolveJobSpec(node: CanvasFlowNode, index: number): CanvasJobSpec {
  const data = node.data as CanvasProcessData;
  const existing = data.job;

  return {
    jobId: existing?.jobId ?? slugFromNode(node, index, "job"),
    jobTitle: existing?.jobTitle ?? `${data.label} Operator`,
    shiftId: existing?.shiftId ?? DEFAULT_SHIFT_ID,
    headcount: existing?.headcount ?? 1,
    demands: existing?.demands ?? {
      requiredCognitiveFocus: 0.5,
      physicalDemandLevel: "medium",
      taskComplexity: 0.5,
      errorSeverity: "moderate",
    },
    qcRequirement: existing?.qcRequirement ?? "visual_inspection",
  };
}

export function resolveStationSpec(node: CanvasFlowNode, index: number): CanvasStationSpec {
  const data = node.data as CanvasProcessData;
  const existing = data.station;
  const stage = resolveStageSpec(node, index);
  const capacity = Math.max(1, stage.throughput.value ?? data.targetOutput ?? 100);

  return {
    materialName: existing?.materialName ?? stage.materialOutput[0] ?? "Material",
    materialUnit: existing?.materialUnit ?? stage.throughput.unit ?? "pcs",
    stepCostBase: existing?.stepCostBase ?? 0,
    capacity: existing?.capacity ?? capacity,
    batchIn: existing?.batchIn ?? Math.max(1, Math.round(capacity / 4)),
    batchOut: existing?.batchOut ?? Math.max(1, Math.round(capacity / 4)),
    cycleTicks: existing?.cycleTicks ?? Math.max(1, Math.round(stage.cycleTimeSeconds / 60)),
  };
}

export interface ResolvedProcessSpecs {
  stage: CanvasStageSpec;
  asset: CanvasAssetSpec;
  job: CanvasJobSpec;
  station: CanvasStationSpec;
}

export function resolveProcessSpecs(node: CanvasFlowNode, index: number): ResolvedProcessSpecs {
  return {
    stage: resolveStageSpec(node, index),
    asset: resolveAssetSpec(node, index),
    job: resolveJobSpec(node, index),
    station: resolveStationSpec(node, index),
  };
}