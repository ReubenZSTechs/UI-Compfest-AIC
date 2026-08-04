import { isAxiosError } from 'axios';
import { apiClient } from '@/api/client';
import { ENDPOINTS } from '@/api/endpoints';
import type {
  ParseJobResult,
  ParseStepId,
  ParseStepStatus,
  ProcessCombinedDocumentsResponse,
} from '../types/documentParser.types';

interface StartParseArgs {
  templateFile: File;
  cvBundleFile: File;
  strict?: boolean;
  maxWorkers?: number;
  maxAttempts?: number;
  onStepUpdate: (step: ParseStepId, status: ParseStepStatus, detail?: string) => void;
}

// Bentuk `detail` di response HTTPException backend FastAPI (HTTP 422)
interface ParseErrorDetail {
  stage?: ParseStepId;
  message?: string;
  details?: string[];
}

// Pipeline backend menjalankan beberapa Agent LLM berurutan (Struktur Pabrik,
// Profil Pekerja, dan Matriks Kompatibilitas N x M).
const PARSE_TIMEOUT_MS = 5 * 60 * 1000; // 5 menit

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
        message:
          'Endpoint document-parser tidak ditemukan (404). Pastikan router document_parser sudah didaftarkan di backend.',
      };
    }

    if (error.code === 'ECONNABORTED') {
      return {
        stage: 'llm_parse',
        message: 'Parsing memakan waktu terlalu lama dan timeout. Coba lagi.',
      };
    }

    if (error.response?.status === 413) {
      return { stage: 'upload', message: 'Berkas terlalu besar untuk diunggah.' };
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
      const { data } = await apiClient.post<
        ProcessCombinedDocumentsResponse | ParseJobResult
      >(endpointUrl, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: PARSE_TIMEOUT_MS,
      });

      let jobId = `job-${Date.now()}`;
      let factoryId: string | null = null;
      let workersParsed = 0;
      let jobDesksParsed = 0;
      let warnings: string[] = [];
      let factoryStructure = null;
      let workerProfile = null;
      let compatibilityMatrix = null;
      let floorState = null;

      // Type narrowing untuk membedakan bentuk data response
      if ('extractionSummary' in data) {
        factoryStructure = data.factoryStructure;
        workerProfile = data.workerProfile;
        compatibilityMatrix = data.compatibilityMatrix;
        warnings = data.extractionSummary?.warnings ?? [];
        workersParsed = data.candidatesFound ?? data.workerProfile?.workers?.length ?? 0;
        jobDesksParsed = data.factoryStructure?.job_desks?.length ?? 0;
        factoryId = data.factoryStructure?.factory_info?.factory_id ?? null;
      } else {
        jobId = data.jobId;
        factoryId = data.factoryId ?? null;
        workersParsed = data.workersParsed;
        jobDesksParsed = data.jobDesksParsed;
        warnings = data.warnings ?? [];
        factoryStructure = data.factoryStructure;
        workerProfile = data.workerProfile;
        compatibilityMatrix = data.compatibilityMatrix;
        floorState = data.floorState ?? null;
      }

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
        jobId,
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

      // Tandai step sebelum stage yang gagal sebagai sukses, stage gagal sebagai error
      const failedIndex = STEP_ORDER.indexOf(stage);
      STEP_ORDER.forEach((step, index) => {
        if (index < failedIndex) {
          onStepUpdate(step, 'success');
        } else if (index === failedIndex) {
          onStepUpdate(step, 'error', message);
        }
      });

      throw new Error(message);
    }
  },
};