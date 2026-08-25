import { useCanvasUIStore } from "@/store/canvasUI";
import { autofillNodeDemands } from "../api/canvasApi";
import { resolveProcessSpecs } from "./processSpecs";
import type {
  AutofillFieldKey,
  CanvasFlowEdge,
  CanvasFlowNode,
  CanvasProcessData,
  NodeAutofillRequest,
  NodeAutofillResponse,
} from "../types/canvas.types";

const MAX_CONCURRENCY = 4;

const TARGET_FIELD_BY_KEY: Record<AutofillFieldKey, string> = {
  requiredSkills: "required_skills",
  operatorTask: "operator_task",
  qcRequirement: "qc_requirement",
  materialInput: "material_input",
  materialOutput: "material_output",
  cycleTimeSeconds: "cycle_time_seconds",
  lane: "lane",
  jobTitle: "job_title",
  headcount: "headcount",
  demands: "demands",
};

const PLACEHOLDER_DEMANDS = {
  requiredCognitiveFocus: 0.5,
  physicalDemandLevel: "medium",
  taskComplexity: 0.5,
  errorSeverity: "moderate",
};

export interface AutofillNodesResult {
  filledNodes: number;
  failures: Array<{ nodeId: string; label: string; message: string }>;
}

type Specs = ReturnType<typeof resolveProcessSpecs>;

function isEmptyText(value: string | undefined | null): boolean {
  return !value || value.trim().length === 0;
}

function isPlaceholderDemands(demands: Specs["job"]["demands"]): boolean {
  return (
    demands.requiredCognitiveFocus === PLACEHOLDER_DEMANDS.requiredCognitiveFocus &&
    demands.taskComplexity === PLACEHOLDER_DEMANDS.taskComplexity &&
    demands.physicalDemandLevel === PLACEHOLDER_DEMANDS.physicalDemandLevel &&
    demands.errorSeverity === PLACEHOLDER_DEMANDS.errorSeverity
  );
}

function isFieldEmpty(key: AutofillFieldKey, data: CanvasProcessData, specs: Specs): boolean {
  switch (key) {
    case "requiredSkills":
      return data.requiredSkills.length === 0;
    case "operatorTask":
      return isEmptyText(specs.stage.operatorTask) || specs.stage.operatorTask === data.label;
    case "qcRequirement":
      return isEmptyText(specs.stage.qcRequirement);
    case "materialInput":
      return specs.stage.materialInput.length === 0;
    case "materialOutput":
      return specs.stage.materialOutput.length === 0;
    case "cycleTimeSeconds":
      return !specs.stage.cycleTimeSeconds || specs.stage.cycleTimeSeconds <= 0;
    case "lane":
      return isEmptyText(specs.stage.lane);
    case "jobTitle":
      return isEmptyText(specs.job.jobTitle);
    case "headcount":
      return !specs.job.headcount || specs.job.headcount < 1;
    case "demands":
      return isPlaceholderDemands(specs.job.demands);
    default:
      return false;
  }
}

function pendingFieldsFor(data: CanvasProcessData, specs: Specs): AutofillFieldKey[] {
  const modes = data.autoFields ?? {};
  const keys = Object.keys(TARGET_FIELD_BY_KEY) as AutofillFieldKey[];

  return keys.filter((key) => modes[key] === "auto" || isFieldEmpty(key, data, specs));
}

function neighbourLabels(
  nodeId: string,
  direction: "up" | "down",
  nodes: CanvasFlowNode[],
  edges: CanvasFlowEdge[]
): string[] {
  return edges
    .filter((edge) => edge.data?.relation === "FLOW")
    .filter((edge) => (direction === "up" ? edge.target === nodeId : edge.source === nodeId))
    .map((edge) => (direction === "up" ? edge.source : edge.target))
    .map((id) => nodes.find((item) => item.id === id))
    .filter((item): item is CanvasFlowNode => Boolean(item))
    .map((item) => item.data.label)
    .filter(Boolean);
}

function buildRequest(
  node: CanvasFlowNode,
  specs: Specs,
  pending: AutofillFieldKey[],
  nodes: CanvasFlowNode[],
  edges: CanvasFlowEdge[]
): NodeAutofillRequest {
  const data = node.data as CanvasProcessData;

  return {
    processName: data.label,
    operatorTask: specs.stage.operatorTask,
    jobTitle: specs.job.jobTitle,
    requiredSkills: data.requiredSkills,
    qcRequirement: specs.stage.qcRequirement,
    assetCategory: specs.asset.category,
    automationLevel: specs.asset.automationLevel,
    cycleTimeSeconds: specs.stage.cycleTimeSeconds || 60,
    noiseLevelDb: specs.asset.environmentalFactors.noiseLevelDb,
    physicalStrainIndex: specs.asset.environmentalFactors.physicalStrainIndex,
    materialInput: specs.stage.materialInput,
    materialOutput: specs.stage.materialOutput,
    headcount: specs.job.headcount || 1,
    upstreamNames: neighbourLabels(node.id, "up", nodes, edges),
    downstreamNames: neighbourLabels(node.id, "down", nodes, edges),
    targetFields: pending
      .filter((key) => key !== "demands")
      .map((key) => TARGET_FIELD_BY_KEY[key]),
  };
}

function applyResponse(
  nodeId: string,
  specs: Specs,
  pending: AutofillFieldKey[],
  response: NodeAutofillResponse
): void {
  const store = useCanvasUIStore.getState();
  const wanted = new Set(pending);
  const suggested = response.suggestions;

  const stagePatch: Partial<Specs["stage"]> = {};
  const jobPatch: Partial<Specs["job"]> = {};
  const dataPatch: Record<string, unknown> = {};

  if (wanted.has("requiredSkills") && suggested.requiredSkills?.length) {
    dataPatch.requiredSkills = suggested.requiredSkills;
  }
  if (wanted.has("operatorTask") && suggested.operatorTask) {
    stagePatch.operatorTask = suggested.operatorTask;
  }
  if (wanted.has("qcRequirement") && suggested.qcRequirement) {
    stagePatch.qcRequirement = suggested.qcRequirement;
    jobPatch.qcRequirement = suggested.qcRequirement;
  }
  if (wanted.has("materialInput") && suggested.materialInput?.length) {
    stagePatch.materialInput = suggested.materialInput;
  }
  if (wanted.has("materialOutput") && suggested.materialOutput?.length) {
    stagePatch.materialOutput = suggested.materialOutput;
  }
  if (wanted.has("cycleTimeSeconds") && suggested.cycleTimeSeconds) {
    stagePatch.cycleTimeSeconds = suggested.cycleTimeSeconds;
  }
  if (wanted.has("lane") && suggested.lane) {
    stagePatch.lane = suggested.lane;
  }
  if (wanted.has("jobTitle") && suggested.jobTitle) {
    jobPatch.jobTitle = suggested.jobTitle;
  }
  if (wanted.has("headcount") && suggested.headcount) {
    jobPatch.headcount = suggested.headcount;
  }
  if (wanted.has("demands")) {
    jobPatch.demands = response.demands;
  }

  if (Object.keys(stagePatch).length > 0) {
    dataPatch.stage = { ...specs.stage, ...stagePatch };
  }
  if (Object.keys(jobPatch).length > 0) {
    dataPatch.job = { ...specs.job, ...jobPatch };
  }
  if (!dataPatch.asset) {
    dataPatch.asset = specs.asset;
  }
  if (!dataPatch.station) {
    dataPatch.station = specs.station;
  }

  store.updateNodeData(nodeId, dataPatch);
}

async function runPool<T>(items: T[], worker: (item: T) => Promise<void>): Promise<void> {
  const queue = [...items];

  const runners = Array.from({ length: Math.min(MAX_CONCURRENCY, queue.length) }, async () => {
    while (queue.length > 0) {
      const item = queue.shift();
      if (item === undefined) return;
      await worker(item);
    }
  });

  await Promise.all(runners);
}

export async function autofillCanvasNodes(
  onProgress?: (done: number, total: number) => void
): Promise<AutofillNodesResult> {
  const store = useCanvasUIStore.getState();
  const { nodes, edges } = store;

  const processNodes = nodes.filter((node) => node.data.kind === "process");
  const jobs: Array<{ node: CanvasFlowNode; specs: Specs; pending: AutofillFieldKey[] }> = [];

  processNodes.forEach((node, index) => {
    const specs = resolveProcessSpecs(node, index);
    const pending = pendingFieldsFor(node.data as CanvasProcessData, specs);
    if (pending.length > 0) jobs.push({ node, specs, pending });
  });

  const failures: AutofillNodesResult["failures"] = [];

  if (jobs.length === 0) {
    return { filledNodes: 0, failures };
  }

  store.snapshot();

  let done = 0;
  let filledNodes = 0;

  await runPool(jobs, async ({ node, specs, pending }) => {
    try {
      const response = await autofillNodeDemands(
        buildRequest(node, specs, pending, nodes, edges)
      );
      applyResponse(node.id, specs, pending, response);
      filledNodes += 1;
    } catch (error) {
      failures.push({
        nodeId: node.id,
        label: node.data.label,
        message: error instanceof Error ? error.message : "Auto-fill gagal.",
      });
    } finally {
      done += 1;
      onProgress?.(done, jobs.length);
    }
  });

  return { filledNodes, failures };
}