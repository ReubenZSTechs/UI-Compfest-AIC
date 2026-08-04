/**
 * src/features/document-parser/types/documentParser.types.ts
 *
 * Definisi tipe data untuk modul document-parser (Tahap 1 - 5 Terpadu).
 */

// --- 1. Status Upload & State UI Pipeline ---

export type UploadStatus = 'idle' | 'selected' | 'error';

export interface UploadSlotState {
  file: File | null;
  status: UploadStatus;
  errorMessage?: string;
}

export type ParseStepId =
  | 'upload'
  | 'extract'
  | 'llm_parse'
  | 'validate'
  | 'compatibility'
  | 'done';

export type ParseStepStatus = 'pending' | 'active' | 'success' | 'error';

export interface ParseStep {
  id: ParseStepId;
  label: string;
  status: ParseStepStatus;
  detail?: string;
}

export type ParseJobStatus = 'idle' | 'running' | 'success' | 'error';


// --- 2. Struktur Data Domain (Pabrik, Worker, Kompatibilitas, & Floor State) ---

export interface FactoryInfo {
  factory_id: string;
  factory_name: string;
  workflow_sequence: string[];
  process_type?: string;
}

export interface FactoryAsset {
  asset_id: string;
  asset_name: string;
  category: string;
  workflow_step: string;
  is_automated: boolean;
  units_available?: number;
  base_throughput_capacity: number;
  operational_cost_per_hour: number;
  environmental_factors?: Record<string, unknown>;
  metric_derivation_reasoning?: string;
}

export interface JobDesk {
  job_id: string;
  job_title: string;
  workflow_step: string;
  assigned_asset_id: string;
  demands?: Record<string, unknown>;
  qc_requirement?: string;
  metric_derivation_reasoning?: string;
}

export interface FactoryStructure {
  factory_info: FactoryInfo;
  assets: FactoryAsset[];
  job_desks: JobDesk[];
  [key: string]: unknown;
}

export interface WorkerRecord {
  worker_id: string;
  name: string;
  demographics?: Record<string, unknown>;
  shift_context?: Record<string, unknown>;
}

export interface WorkerProfile {
  workers: WorkerRecord[];
  [key: string]: unknown;
}

export interface CompatibilityEntry {
  job_title?: string;
  asset_id?: string;
  evaluations?: Record<string, unknown>;
  llm_reasoning?: string;
  attempts?: number;
}

export interface CompatibilityWorkerRecord {
  worker_name?: string;
  best_job_id?: string;
  jobs: Record<string, CompatibilityEntry>;
}

export interface CompatibilityMatrix {
  compatibility_matrix: Record<string, CompatibilityWorkerRecord>;
  meta?: {
    evaluated_pairs?: number;
    retries?: number;
    failed_pairs?: unknown[];
  };
}

export interface StaffPosition {
  worker_id: string;
  current_station?: string;
  current_asset_id?: string;
  activity_status?: string;
  moving_to_next_step?: string;
  handoff_item?: string;
}

export interface FloorState {
  snapshot_timestamp?: string;
  note?: string;
  staff_current_positions?: StaffPosition[];
  [key: string]: unknown;
}


// --- 3. Skema Respons Endpoint Combined Pipeline (Tahap 1, 2, 4, & 5) ---

export interface ExtractionSummary {
  extractedFields: Record<string, string>;
  tablesCount: number;
  rawText?: string | null;
  warnings: string[];
}

export interface ArchiveReportSummary {
  archiveName: string;
  acceptedCount: number;
  skipped: Array<Record<string, unknown>>;
  failed: Array<Record<string, unknown>>;
}

export interface ProcessCombinedDocumentsResponse {
  // Hasil Pabrik (Tahap 1 & 2)
  extractionSummary: ExtractionSummary;
  agentInput: string;
  factoryStructure: FactoryStructure;

  // Hasil Worker (Tahap 4)
  workerProfile: WorkerProfile;
  workerAgentInput: string;
  candidatesFound: number;
  rejectedBlocksCount: number;
  archiveReports: ArchiveReportSummary[];

  // Matriks Kompatibilitas (Tahap 5)
  compatibilityMatrix: CompatibilityMatrix;
}

export interface ProcessCombinedParams {
  strict?: boolean;
  maxWorkers?: number;
  maxAttempts?: number;
}


// --- 4. Result & Error Job Handling ---

export interface ParseJobResult {
  jobId: string;
  factoryId?: string | null;
  workersParsed: number;
  jobDesksParsed: number;
  warnings: string[];
  factoryStructure: FactoryStructure | null;
  workerProfile: WorkerProfile | null;
  compatibilityMatrix: CompatibilityMatrix | null;
  floorState: FloorState | null;
}

export interface DocumentParserErrorDetail {
  stage: ParseStepId;
  message: string;
  details?: unknown[];
}