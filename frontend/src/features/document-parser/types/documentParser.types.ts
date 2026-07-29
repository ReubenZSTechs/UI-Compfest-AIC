export type UploadStatus = 'idle' | 'selected' | 'error';

export interface UploadSlotState {
  file: File | null;
  status: UploadStatus;
  errorMessage?: string;
}

export type ParseStepId = 'upload' | 'extract' | 'llm_parse' | 'validate' | 'done';

export type ParseStepStatus = 'pending' | 'active' | 'success' | 'error';

export interface ParseStep {
  id: ParseStepId;
  label: string;
  status: ParseStepStatus;
  detail?: string;
}

export type ParseJobStatus = 'idle' | 'running' | 'success' | 'error';

export interface ParseJobResult {
  jobId: string;
  workersParsed: number;
  jobDesksParsed: number;
  warnings: string[];
}