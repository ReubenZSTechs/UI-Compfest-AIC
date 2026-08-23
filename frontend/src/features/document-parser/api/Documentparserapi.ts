// src/features/document-parser/api/documentParser.api.ts

import { isAxiosError } from 'axios';
import { apiClient } from '@/api/client';
import { ENDPOINTS } from '@/api/endpoints';
import type {
  ParseJobResult,
  ParseStepId,
  ParseStepStatus,
} from '../types/documentParser.types';

interface StartParseArgs {
  templateFile: File;
  cvBundleFile: File;
  strict?: boolean;
  maxWorkers?: number;
  maxAttempts?: number;
  onStepUpdate: (step: ParseStepId, status: ParseStepStatus, detail?: string) => void;
}

interface ParseErrorDetail {
  stage?: ParseStepId;
  message?: string;
  details?: string[];
}

const PARSE_TIMEOUT_MS = 25 * 60 * 1000;

const STEP_ORDER: ParseStepId[] = [
  'upload',
  'extract',
  'llm_parse',
  'validate',
  'compatibility',
  'done',
];

function isParseStepId(value: string | undefined): value is ParseStepId {
  return !!value && (STEP_ORDER as string[]).includes(value);
}

function parseErrorResponse(error: unknown): { stage: ParseStepId; message: string } {
  if (isAxiosError<{ detail?: ParseErrorDetail | string }>(error)) {
    const detail = error.response?.data?.detail;

    if (typeof detail === 'object' && detail !== null) {
      const stage = isParseStepId(detail.stage) ? detail.stage : 'upload';
      const detailLines = detail.details?.length ? `: ${detail.details.join('; ')}` : '';
      return { stage, message: `${detail.message ?? 'Parsing gagal.'}${detailLines}` };
    }

    if (typeof detail === 'string') {
      return { stage: 'upload', message: detail };
    }

    if (error.response?.status === 404) {
      return {
        stage: 'upload',
        message: 'Endpoint document-parser tidak ditemukan (404).',
      };
    }

    if (error.code === 'ECONNABORTED') {
      return {
        stage: 'llm_parse',
        message: 'Parsing memakan waktu terlalu lama dan timeout. Coba lagi.',
      };
    }
  }

  return { stage: 'upload', message: 'Terjadi kesalahan tak terduga saat parsing.' };
}

export const documentParserApi = {
  parse: async ({
    templateFile,
    cvBundleFile,
    strict = false,
    maxWorkers = 4,
    maxAttempts = 3,
    onStepUpdate,
  }: StartParseArgs): Promise<ParseJobResult> => {
    const formData = new FormData();
    formData.append('template', templateFile);
    formData.append('worker_zip', cvBundleFile);

    const queryParams = new URLSearchParams({
      strict: String(strict),
      max_workers: String(maxWorkers),
      max_attempts: String(maxAttempts),
    });

    const endpointUrl = `${ENDPOINTS.DOCUMENT_PARSER.PROCESS_COMBINED}?${queryParams.toString()}`;

    onStepUpdate('upload', 'active');

    try {
      // Backend mengembalikan bentuk response yang tidak konsisten (snake_case/
      // camelCase campur, field opsional berbeda per jalur pipeline) -- lihat
      // akses properti longgar di bawah. Mengetatkan ini butuh mendefinisikan
      // union type penuh untuk seluruh kemungkinan bentuk response backend
      // (pipeline kombinasi vs per-tahap), di luar scope perbaikan lint kali ini.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const { data } = await apiClient.post<Record<string, any>>(endpointUrl, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: PARSE_TIMEOUT_MS,
      });

      // Backend baru mengembalikan `simulation_id` dan membungkus hasil LLM di `data`
      const simulationId = data.simulation_id ?? data.job_id ?? data.jobId ?? `sim-${Date.now()}`;
      const factoryId = data.factory_id ?? data.factoryId ?? null;
      const workersParsed = data.workers_parsed ?? data.workersParsed ?? 0;
      const jobDesksParsed = data.job_desks_parsed ?? data.jobDesksParsed ?? 0;
      const warnings: string[] = data.warnings ?? [];

      // Ekstrak payload LLM dari properti `data` (jika ada) atau dari top-level
      const nestedData = data.data ?? data;
      const factoryStructure = nestedData.factory_structure ?? nestedData.factoryStructure ?? null;
      const workerProfile = nestedData.worker_profile ?? nestedData.workerProfile ?? null;
      const compatibilityMatrix = nestedData.compatibility_matrix ?? nestedData.compatibilityMatrix ?? null;
      const floorState = nestedData.floor_state ?? nestedData.floorState ?? null;

      // Update indikator UI bertahap setelah request sukses
      onStepUpdate('upload', 'success');
      onStepUpdate('extract', 'success');
      onStepUpdate('llm_parse', 'success');
      onStepUpdate(
        'validate',
        'success',
        warnings.length > 0 ? `${warnings.length} peringatan` : undefined
      );
      onStepUpdate('compatibility', 'success', 'Matriks kompatibilitas terbentuk');
      onStepUpdate(
        'done',
        'success',
        `${workersParsed} pekerja, ${jobDesksParsed} job desk tersimpan`
      );

      return {
        jobId: simulationId, // Tetap dipetakan ke jobId agar kompatibel dengan komponen UI
        simulationId,       // Menyimpan simulation_id secara eksplisit
        factoryId,
        workersParsed,
        jobDesksParsed,
        warnings,
        factoryStructure,
        workerProfile,
        compatibilityMatrix,
        floorState,
      };
    } catch (error) {
      const { stage, message } = parseErrorResponse(error);

      const failedIndex = STEP_ORDER.indexOf(stage);
      STEP_ORDER.forEach((step, index) => {
        if (index < failedIndex) {
          onStepUpdate(step, 'success');
        } else if (index === failedIndex) {
          onStepUpdate(step, 'error', message);
        }
      });

      throw new Error(message, { cause: error });
    }
  },
};