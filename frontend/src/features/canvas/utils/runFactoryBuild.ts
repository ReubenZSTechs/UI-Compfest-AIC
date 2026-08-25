import { useCanvasUIStore } from "@/store/canvasUI";
import {
  createFactory,
  enqueueCompatibilityJob,
  saveSimulationDesign,
} from "../api/canvasApi";
import { buildSimulationDesignPayload, validateDesignInput } from "./designPayload";
import { computeExecutionRounds, toFlowGraph } from "./flowLogic";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export interface FactoryBuildResult {
  status: "done" | "error";
  message: string;
  factoryId?: string;
  compatibilityJobId?: string;
}

async function animateVerification(signal?: AbortSignal): Promise<void> {
  const store = useCanvasUIStore.getState();
  const rounds = computeExecutionRounds(toFlowGraph(store.nodes, store.edges));

  for (const round of rounds) {
    if (signal?.aborted) return;
    for (const id of round) {
      store.updateNodeData(id, { aiStatus: "analyzing" });
    }
    await delay(280);
    for (const id of round) {
      store.updateNodeData(id, { aiStatus: "verified" });
    }
    await delay(140);
  }

  for (const node of store.nodes) {
    if (node.data.kind === "output") {
      store.updateNodeData(node.id, { aiStatus: "verified" });
    }
  }
}

export async function runFactoryBuild(signal?: AbortSignal): Promise<FactoryBuildResult> {
  const store = useCanvasUIStore.getState();
  const {
    nodes,
    edges,
    factoryMeta,
    shifts,
    simulationSettings,
    workerAssignments,
    projectTitle,
  } = store;

  const input = {
    nodes,
    edges,
    factoryMeta,
    shifts,
    settings: simulationSettings,
    workerAssignments,
  };

  const issues = validateDesignInput(input);
  if (issues.length > 0) {
    for (const issue of issues) {
      if (issue.nodeId) store.updateNodeData(issue.nodeId, { aiStatus: "error" });
    }
    const message = issues.map((issue) => issue.message).join(" ");
    store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
    return { status: "error", message };
  }

  store.setAnalysis({ status: "running", message: "Menyiapkan factory..." });
  for (const node of nodes) {
    store.updateNodeData(node.id, { aiStatus: "analyzing" });
  }

  try {
    store.setBuildProgress({ stage: "factory", status: "active", message: "Membuat factory_id" });

    let factoryId = store.factoryId;
    if (!factoryId) {
      const summary = await createFactory({
        factoryName: factoryMeta.factoryName || projectTitle,
        processType: factoryMeta.processType,
        declaredWorkerCount: factoryMeta.declaredWorkerCount,
        layoutDescription: factoryMeta.layoutDescription,
      });
      factoryId = summary.factoryId;
      store.setFactoryId(factoryId);
    }
    store.setBuildProgress({ stage: "factory", status: "success", message: factoryId });

    store.setAnalysis({ status: "running", message: "Menyimpan rancangan flowchart..." });
    store.setBuildProgress({ stage: "design", status: "active", message: null });

    const payload = buildSimulationDesignPayload(input);
    const design = await saveSimulationDesign(factoryId, payload);

    store.setBuildProgress({
      stage: "design",
      status: "success",
      message: `${design.processStagesSaved} stage, ${design.jobDesksSaved} job desk tersimpan`,
    });

    store.setAnalysis({ status: "running", message: "Menjadwalkan matriks kompatibilitas..." });
    store.setBuildProgress({ stage: "compatibility", status: "active", message: null });

    const job = await enqueueCompatibilityJob(factoryId);
    store.setBuildProgress({ stage: "compatibility", status: "success", message: job.jobId });

    await animateVerification(signal);

    const message =
      design.warnings.length > 0
        ? `Rancangan tersimpan dengan ${design.warnings.length} peringatan.`
        : "Rancangan tersimpan dan matriks kompatibilitas dijadwalkan.";

    store.setAnalysis({ status: "done", message, finishedAt: new Date().toISOString() });
    store.setBuildProgress({ stage: "done", status: "success", message });

    return { status: "done", message, factoryId, compatibilityJobId: job.jobId };
  } catch (error) {
    for (const node of nodes) {
      store.updateNodeData(node.id, { aiStatus: "error" });
    }
    const message = error instanceof Error ? error.message : "Pembuatan digital twin gagal.";
    store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
    store.setBuildProgress({ status: "error", message });
    return { status: "error", message };
  }
}