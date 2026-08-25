import { useCallback, useEffect, useRef, useState } from "react";
import { getCompatibilityJob, getFactorySummary } from "@/features/canvas/api/canvasApi";
import type { CompatibilityJob, FactorySummary } from "@/features/canvas/api/canvasApi";

export type BuildStepId = "factory" | "design" | "workers" | "compatibility" | "done";
export type BuildStepStatus = "pending" | "active" | "success" | "error";

export interface BuildStep {
  id: BuildStepId;
  label: string;
  status: BuildStepStatus;
  detail?: string;
}

const POLL_INTERVAL_MS = 2500;

const INITIAL_STEPS: BuildStep[] = [
  { id: "factory", label: "Inisialisasi Factory", status: "pending" },
  { id: "workers", label: "Profil Pekerja", status: "pending" },
  { id: "design", label: "Rancangan Flowchart", status: "pending" },
  { id: "compatibility", label: "Matriks Kompatibilitas", status: "pending" },
  { id: "done", label: "Selesai", status: "pending" },
];

function buildSteps(summary: FactorySummary | null, job: CompatibilityJob | null): BuildStep[] {
  return INITIAL_STEPS.map((step) => {
    if (step.id === "factory") {
      return summary
        ? { ...step, status: "success", detail: summary.factoryId }
        : { ...step, status: "active" };
    }
    if (step.id === "workers") {
      return summary && summary.workersCount > 0
        ? { ...step, status: "success", detail: `${summary.workersCount} pekerja` }
        : { ...step, status: summary ? "error" : "pending", detail: "Belum ada worker terdaftar" };
    }
    if (step.id === "design") {
      return summary?.simulationConfigured
        ? { ...step, status: "success", detail: `${summary.processStagesCount} stage` }
        : { ...step, status: summary ? "active" : "pending" };
    }
    if (step.id === "compatibility") {
      if (!job) return { ...step, status: "pending" };
      if (job.status === "error") {
        return { ...step, status: "error", detail: job.errorMessage ?? "Job gagal" };
      }
      if (job.status === "success") {
        return { ...step, status: "success", detail: `${job.evaluationsPersisted} evaluasi` };
      }
      return { ...step, status: "active", detail: `${job.progressPercent.toFixed(0)}%` };
    }
    return job?.status === "success"
      ? { ...step, status: "success" }
      : { ...step, status: "pending" };
  });
}

export function useFactoryBuildStatus(factoryId: string | null, compatibilityJobId: string | null) {
  const [summary, setSummary] = useState<FactorySummary | null>(null);
  const [job, setJob] = useState<CompatibilityJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);
  const timerRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!factoryId) return;
    try {
      const nextSummary = await getFactorySummary(factoryId);
      setSummary(nextSummary);

      if (!compatibilityJobId) return;

      const nextJob = await getCompatibilityJob(compatibilityJobId);
      setJob(nextJob);

      if (nextJob.status === "queued" || nextJob.status === "running") {
        timerRef.current = window.setTimeout(() => void refresh(), POLL_INTERVAL_MS);
      } else {
        stopPolling();
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Gagal memuat status pembangunan.");
      stopPolling();
    }
  }, [factoryId, compatibilityJobId, stopPolling]);

  useEffect(() => {
    void refresh();
    return stopPolling;
  }, [refresh, stopPolling]);

  const steps = buildSteps(summary, job);
  const jobStatus =
    errorMessage || job?.status === "error"
      ? "error"
      : job?.status === "success"
        ? "success"
        : factoryId
          ? "running"
          : "idle";

  return {
    steps,
    jobStatus,
    summary,
    job,
    errorMessage: errorMessage ?? job?.errorMessage ?? undefined,
    retry: refresh,
    hasContext: Boolean(factoryId),
  };
}