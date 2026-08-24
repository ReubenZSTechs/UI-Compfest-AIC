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

/**
 * Payload JSON hasil ekstraksi dokumen yang sudah dilakukan pada halaman
 * sebelumnya (upload + ekstraksi template pabrik & bundel CV karyawan).
 * `DocumentParserPage` tidak lagi menangani upload berkas mentah -- ia hanya
 * menerima struktur ini (via route state) dan meneruskannya ke pipeline
 * tahap 1 - 5 (LLM parse -> validasi -> matriks kompatibilitas).
 *
 * Sesuaikan bentuk field di bawah ini dengan kontrak nyata dari halaman
 * upload/ekstraksi & endpoint backend yang menerimanya.
 */
export interface DocumentIngestionPayload {
  /** Hasil ekstraksi template dokumen pabrik (workflow, aset, job desk mentah). */
  templateData: Record<string, unknown>;
  /** Hasil ekstraksi bundel CV karyawan (per-worker, sudah dalam bentuk JSON). */
  workerCvData: Record<string, unknown>;
  /** Metadata opsional yang dibawa dari halaman upload (mis. nama sumber berkas). */
  sourceMeta?: {
    templateFileName?: string;
    cvBundleFileName?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
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
  declared_worker_count?: number;
  layout_description?: string;
  parallel_groups?: Array<{
    group_id?: string;
    steps?: string[];
    reasoning?: string;
  }>;
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
  environmental_factors?: {
    noise_level_db?: number;
    vibration_hazard_level?: string;
    [key: string]: unknown;
  };
  metric_derivation_reasoning?: string;
}

export interface JobDesk {
  job_id: string;
  job_title: string;
  workflow_step: string;
  assigned_asset_id: string;
  demands?: {
    physical_demand_level?: string;
    required_cognitive_focus?: string;
    task_complexity?: string;
    [key: string]: unknown;
  };
  qc_requirement?: string;
  metric_derivation_reasoning?: string;
}

export interface FactoryStructure {
  factory_info: FactoryInfo;
  assets: FactoryAsset[];
  job_desks: JobDesk[];
  job_descriptions?: JobDesk[]; // Fallback jika agent menggunakan key 'job_descriptions'
  [key: string]: unknown;
}

export interface WorkerRecord {
  worker_id: string;
  name: string;
  demographics?: {
    age?: number;
    gender?: string;
    years_of_experience?: number;
    baseline_physical_stamina?: number;
    cognitive_resilience?: number;
    [key: string]: unknown;
  };
  shift_context?: {
    hours_worked_today?: number;
    consecutive_shifts?: number;
    [key: string]: unknown;
  };
  skills?: string[];
  capabilities?: string[];
  certifications?: string[];
}

export interface WorkerProfile {
  workers: WorkerRecord[];
  [key: string]: unknown;
}

export interface CompatibilityEvaluationDetail {
  overall_compatibility_score?: number;
  throughput_multiplier?: number;
  error_multiplier?: number;
  [key: string]: unknown;
}

export interface CompatibilityEntry {
  job_title?: string;
  asset_id?: string;
  evaluations?: CompatibilityEvaluationDetail;
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
    worker_count?: number;
    job_count?: number;
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


// --- 3. Skema Respons Endpoint Combined Pipeline (Backend REST Payload) ---

export interface ExtractionSummary {
  extracted_fields?: Record<string, string>;
  tables_count?: number;
  raw_text?: string | null;
  warnings?: string[];
}

export interface ArchiveReportSummary {
  archive_name: string;
  accepted_count: number;
  skipped: Array<Record<string, unknown>>;
  failed: Array<Record<string, unknown>>;
}

export interface CombinedPipelineData {
  extraction_summary?: ExtractionSummary;
  agent_input?: string;
  factory_structure?: FactoryStructure;
  worker_profile?: WorkerProfile;
  worker_agent_input?: string;
  candidates_found?: number;
  rejected_blocks_count?: number;
  archive_reports?: ArchiveReportSummary[];
  compatibility_matrix?: CompatibilityMatrix;
  [key: string]: unknown;
}

export interface ProcessCombinedDocumentsResponse {
  simulation_id: string;
  factory_id: string | null;
  status: string;
  workers_parsed: number;
  job_desks_parsed: number;
  warnings: string[];
  data?: CombinedPipelineData;
}

export interface ProcessCombinedParams {
  strict?: boolean;
  maxWorkers?: number;
  maxAttempts?: number;
}


// --- 4. Result & Error Job Handling (Normalized Frontend State) ---

export interface ParseJobResult {
  jobId: string;          // Alias ke simulationId demi kompatibilitas UI
  simulationId: string;   // Unique UUID simulation_id dari database
  factoryId: string | null;
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

/** State yang dibawa lewat navigasi (react-router `location.state`) menuju DocumentParserPage. */
export interface DocumentParserPageLocationState {
  documentPayload: DocumentIngestionPayload;
}