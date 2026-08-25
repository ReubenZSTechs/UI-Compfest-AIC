import { useCanvasUIStore } from "@/store/canvasUI";
import type { ApiError } from "@/api/client";
import {
  createFactory,
  enqueueCompatibilityJob,
  getFactorySummary,
  saveSimulationDesign,
} from "../api/canvasApi";
import { autofillCanvasNodes } from "./autofillNodes";
import { buildSimulationDesignPayload, validateDesignInput } from "./designPayload";
import { computeExecutionRounds, toFlowGraph } from "./flowLogic";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export interface FactoryBuildResult {
  status: "done" | "error";
  message: string;
  factoryId?: string;
  compatibilityJobId?: string;
}

interface FactoryMetaInput {
  factoryName: string;
  processType: "serial" | "parallel" | "hybrid";
  declaredWorkerCount: number;
  layoutDescription: string;
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

  for (const node of useCanvasUIStore.getState().nodes) {
    if (node.data.kind === "output") {
      store.updateNodeData(node.id, { aiStatus: "verified" });
    }
  }
}

async function resolveFactoryId(
  storedId: string | null,
  meta: FactoryMetaInput
): Promise<{ factoryId: string; recreated: boolean }> {
  if (storedId) {
    try {
      const summary = await getFactorySummary(storedId);
      return { factoryId: summary.factoryId, recreated: false };
    } catch (error) {
      if ((error as ApiError).status !== 404) throw error;
    }
  }

  const summary = await createFactory(meta);
  return { factoryId: summary.factoryId, recreated: true };
}

export async function runFactoryBuild(signal?: AbortSignal): Promise<FactoryBuildResult> {
  const store = useCanvasUIStore.getState();

  if (store.nodes.length === 0) {
    const message = "Kanvas masih kosong.";
    store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
    return { status: "error", message };
  }

  store.setAnalysis({ status: "running", message: "Melengkapi detail node…" });
  for (const node of store.nodes) {
    store.updateNodeData(node.id, { aiStatus: "analyzing" });
  }

  const buildWarnings: string[] = [];

  try {
    store.setBuildProgress({
      stage: "autofill",
      status: "active",
      message: "Menjalankan agent auto-fill",
    });

    const autofill = await autofillCanvasNodes((done, total) => {
      store.setBuildProgress({
        stage: "autofill",
        status: "active",
        message: `Auto-fill node ${done}/${total}`,
      });
    });

    if (autofill.failures.length > 0) {
      buildWarnings.push(
        `${autofill.failures.length} node gagal di-autofill: ` +
          autofill.failures.map((item) => item.label).join(", ")
      );
    }

    store.setBuildProgress({
      stage: "autofill",
      status: "success",
      message:
        autofill.filledNodes > 0
          ? `${autofill.filledNodes} node dilengkapi agent`
          : "Semua node sudah lengkap",
    });

    const fresh = useCanvasUIStore.getState();
    const input = {
      nodes: fresh.nodes,
      edges: fresh.edges,
      factoryMeta: fresh.factoryMeta,
      shifts: fresh.shifts,
      settings: fresh.simulationSettings,
      workerAssignments: fresh.workerAssignments,
      shiftAssignments: fresh.shiftAssignments,
      workerPool: fresh.workerPool,
    };

    const issues = validateDesignInput(input);
    if (issues.length > 0) {
      for (const issue of issues) {
        if (issue.nodeId) store.updateNodeData(issue.nodeId, { aiStatus: "error" });
      }
      const message = issues.map((issue) => issue.message).join(" ");
      store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
      store.setBuildProgress({ status: "error", message });
      return { status: "error", message };
    }

    store.setAnalysis({ status: "running", message: "Menyiapkan factory..." });
    store.setBuildProgress({
      stage: "factory",
      status: "active",
      message: "Memverifikasi factory_id",
    });

    const { factoryId, recreated } = await resolveFactoryId(fresh.factoryId, {
      factoryName: fresh.factoryMeta.factoryName || fresh.projectTitle,
      processType: fresh.factoryMeta.processType,
      declaredWorkerCount: fresh.factoryMeta.declaredWorkerCount,
      layoutDescription: fresh.factoryMeta.layoutDescription,
    });

    if (recreated) {
      store.setFactoryId(factoryId);
      if (fresh.factoryId && fresh.factoryId !== factoryId) {
        buildWarnings.push(
          `factory_id lama '${fresh.factoryId}' tidak valid di backend; factory baru dibuat.`
        );
      }
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

    const warnings = [...buildWarnings, ...design.warnings];
    const message =
      warnings.length > 0
        ? `Rancangan tersimpan dengan ${warnings.length} peringatan: ${warnings.join(" ")}`
        : "Rancangan tersimpan dan matriks kompatibilitas dijadwalkan.";

    store.setAnalysis({ status: "done", message, finishedAt: new Date().toISOString() });
    store.setBuildProgress({ stage: "done", status: "success", message });

    return { status: "done", message, factoryId, compatibilityJobId: job.jobId };
  } catch (error) {
    for (const node of useCanvasUIStore.getState().nodes) {
      store.updateNodeData(node.id, { aiStatus: "error" });
    }
    const message = error instanceof Error ? error.message : "Pembuatan digital twin gagal.";
    store.setAnalysis({ status: "error", message, finishedAt: new Date().toISOString() });
    store.setBuildProgress({ status: "error", message });
    return { status: "error", message };
  }
}