import { apiClient } from '@/api/client';
import type { ParseJobResult, ParseStepId, ParseStepStatus } from '../types/documentParser.types';

interface StartParseArgs {
  templateFile: File;
  cvBundleFile: File;
  onStepUpdate: (step: ParseStepId, status: ParseStepStatus, detail?: string) => void;
}

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function startParseJob(args: StartParseArgs): Promise<ParseJobResult> {
  if (USE_MOCK) {
    return mockParseJob(args);
  }
  return realParseJob(args);
}

async function realParseJob({ templateFile, cvBundleFile, onStepUpdate }: StartParseArgs): Promise<ParseJobResult> {
  const formData = new FormData();
  formData.append('template', templateFile);
  formData.append('cv_bundle', cvBundleFile);

  onStepUpdate('upload', 'active');
  try {
    // TODO: pindahkan path ini ke api/endpoints.ts (API_ENDPOINTS.documentParser.parse)
    // begitu endpoint backend untuk document-parser sudah siap. Endpoint disini
    // diasumsikan synchronous dan mengembalikan hasil akhir langsung (belum via WS).
    const { data } = await apiClient.post<ParseJobResult>('/document-parser/parse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    onStepUpdate('upload', 'success');
    onStepUpdate('extract', 'success');
    onStepUpdate('llm_parse', 'success');
    onStepUpdate('validate', 'success');
    onStepUpdate('done', 'success');
    return data;
  } catch (error) {
    onStepUpdate('upload', 'error');
    throw error;
  }
}

async function mockParseJob({ templateFile, cvBundleFile, onStepUpdate }: StartParseArgs): Promise<ParseJobResult> {
  onStepUpdate('upload', 'active');
  await delay(500);
  onStepUpdate('upload', 'success', `${templateFile.name} + ${cvBundleFile.name}`);

  onStepUpdate('extract', 'active');
  await delay(700);
  onStepUpdate('extract', 'success', 'Teks & struktur tabel diekstrak');

  onStepUpdate('llm_parse', 'active');
  await delay(1000);
  onStepUpdate('llm_parse', 'success', 'Digital twin JSON tersusun');

  onStepUpdate('validate', 'active');
  await delay(500);
  onStepUpdate('validate', 'success', 'Skema tervalidasi, 0 error kritikal');

  onStepUpdate('done', 'success');

  return {
    jobId: `job-${Date.now()}`,
    workersParsed: 10,
    jobDesksParsed: 10,
    warnings: [],
  };
}