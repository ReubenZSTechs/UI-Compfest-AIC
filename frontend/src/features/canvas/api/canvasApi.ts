import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type { CanvasWorkerProfile } from "../types/canvas.types";
import type { SimulationDesignPayload } from "../utils/designPayload";
import type { NodeAutofillRequest, NodeAutofillResponse } from "../types/canvas.types";

const AUTOFILL_TIMEOUT_MS = 90 * 1000;

export interface FactorySummary {
  factoryId: string;
  factoryName: string;
  processType: string;
  status: string;
  declaredWorkerCount: number;
  registeredWorkerCount: number;
  assetsCount: number;
  processStagesCount: number;
  shiftsCount: number;
  jobDesksCount: number;
  workersCount: number;
  evaluationsCount: number;
  simulationConfigured: boolean;
  createdAt?: string | null;
}

export interface CreateFactoryPayload {
  factoryName: string;
  processType: "serial" | "parallel" | "hybrid";
  declaredWorkerCount: number;
  layoutDescription: string;
}

export interface WorkerArchiveResult {
  factoryId: string | null;
  workers: CanvasWorkerProfile[];
  candidatesFound: number;
  workersPersisted: number;
  rejectedBlocksCount: number;
  warnings: string[];
}

export interface SimulationDesignResult {
  factoryId: string;
  assetsSaved: number;
  processStagesSaved: number;
  shiftsSaved: number;
  jobDesksSaved: number;
  stationsSaved: number;
  workerMultipliersSaved: number;
  seedAssignmentsSaved: number;
  warnings: string[];
}

export interface CompatibilityJob {
  jobId: string;
  factoryId: string;
  status: "queued" | "running" | "success" | "error";
  totalPairs: number;
  completedPairs: number;
  progressPercent: number;
  evaluationsPersisted: number;
  warnings: string[];
  errorStage?: string | null;
  errorMessage?: string | null;
}

const ARCHIVE_TIMEOUT_MS = 10 * 60 * 1000;
const DESIGN_TIMEOUT_MS = 60 * 1000;

function toStringArray(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is string => typeof item === "string");
}

function toRecord(raw: unknown): Record<string, unknown> {
  return raw && typeof raw === "object" && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : {};
}

function normalizeWorkerProfile(raw: unknown, index: number): CanvasWorkerProfile {
  const entry = toRecord(raw);
  const workerId =
    (entry.worker_id as string) ?? (entry.workerId as string) ?? `wrk-${index + 1}`;

  return {
    workerId,
    name: (entry.name as string) ?? workerId,
    skills: toStringArray(entry.skills),
    certifications: toStringArray(entry.certifications),
    capabilities: toStringArray(entry.capabilities),
    demographics: toRecord(entry.demographics ?? entry.demographic),
    shiftContext: toRecord(entry.shift_context ?? entry.shiftContext),
    sourceFile: (entry.source_file as string) ?? (entry.sourceFile as string) ?? undefined,
  };
}

function extractWorkers(workerProfile: unknown): CanvasWorkerProfile[] {
  const profile = toRecord(workerProfile);
  const rows = Array.isArray(profile.workers) ? profile.workers : [];
  return rows.map(normalizeWorkerProfile);
}

export async function createFactory(payload: CreateFactoryPayload): Promise<FactorySummary> {
  const { data } = await apiClient.post<FactorySummary>(ENDPOINTS.FACTORIES.ROOT, payload);
  return data;
}

export async function getFactorySummary(factoryId: string): Promise<FactorySummary> {
  const { data } = await apiClient.get<FactorySummary>(ENDPOINTS.FACTORIES.DETAIL(factoryId));
  return data;
}

export async function uploadWorkerArchive(
  factoryId: string,
  file: File,
  options: { strict?: boolean; maxWorkers?: number; maxAttempts?: number } = {}
): Promise<WorkerArchiveResult> {
  const formData = new FormData();
  formData.append("worker_zip", file);

  const { data } = await apiClient.post<Record<string, unknown>>(
    ENDPOINTS.DOCUMENTS.STEP_4,
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: ARCHIVE_TIMEOUT_MS,
      params: {
        factory_id: factoryId,
        strict: options.strict ?? false,
        max_workers: options.maxWorkers ?? 4,
        max_attempts: options.maxAttempts ?? 3,
      },
    }
  );

  return {
    factoryId: (data.factoryId as string) ?? factoryId,
    workers: extractWorkers(data.workerProfile),
    candidatesFound: (data.candidatesFound as number) ?? 0,
    workersPersisted: (data.workersPersisted as number) ?? 0,
    rejectedBlocksCount: (data.rejectedBlocksCount as number) ?? 0,
    warnings: toStringArray(data.warnings),
  };
}

export async function saveSimulationDesign(
  factoryId: string,
  payload: SimulationDesignPayload
): Promise<SimulationDesignResult> {
  const { data } = await apiClient.put<SimulationDesignResult>(
    ENDPOINTS.FACTORIES.SIMULATION_DESIGN(factoryId),
    payload,
    { timeout: DESIGN_TIMEOUT_MS }
  );
  return data;
}

export async function enqueueCompatibilityJob(
  factoryId: string,
  options: { maxWorkers?: number; maxAttempts?: number; strictCompatibility?: boolean } = {}
): Promise<CompatibilityJob> {
  const { data } = await apiClient.post<CompatibilityJob>(ENDPOINTS.DOCUMENTS.STEP_5_JOBS, {
    factoryId,
    maxWorkers: options.maxWorkers ?? 4,
    maxAttempts: options.maxAttempts ?? 3,
    strictCompatibility: options.strictCompatibility ?? false,
    persist: true,
  });
  return data;
}

export async function getCompatibilityJob(jobId: string): Promise<CompatibilityJob> {
  const { data } = await apiClient.get<CompatibilityJob>(ENDPOINTS.DOCUMENTS.STEP_5_JOB(jobId));
  return data;
}

export async function cancelCompatibilityJob(jobId: string): Promise<CompatibilityJob> {
  const { data } = await apiClient.delete<CompatibilityJob>(ENDPOINTS.DOCUMENTS.STEP_5_JOB(jobId));
  return data;
}

export async function autofillNodeDemands(
  payload: NodeAutofillRequest
): Promise<NodeAutofillResponse> {
  const { data } = await apiClient.post<NodeAutofillResponse>(
    ENDPOINTS.AGENTS.NODE_AUTOFILL,
    payload,
    { timeout: AUTOFILL_TIMEOUT_MS }
  );
  return data;
}