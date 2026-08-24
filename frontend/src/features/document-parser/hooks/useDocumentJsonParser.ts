import { useCallback, useEffect, useRef, useState } from 'react';
import { documentParserApi } from '../api/Documentparserapi';
import type {
  DocumentIngestionPayload,
  ParseJobResult,
  ParseJobStatus,
  ParseStep,
  ParseStepId,
  ParseStepStatus,
} from '../types/documentParser.types';

const INITIAL_STEPS: ParseStep[] = [
  { id: 'upload', label: 'Unggah Berkas', status: 'pending' },
  { id: 'extract', label: 'Ekstraksi Konten', status: 'pending' },
  { id: 'llm_parse', label: 'Parsing LLM', status: 'pending' },
  { id: 'validate', label: 'Validasi Skema', status: 'pending' },
  { id: 'compatibility', label: 'Matriks Kompatibilitas', status: 'pending' },
  { id: 'done', label: 'Selesai', status: 'pending' },
];

const STEP_ORDER: ParseStepId[] = INITIAL_STEPS.map((step) => step.id);

/**
 * DEV-ONLY BYPASS: aktifkan dengan menambahkan `?mock=success` di URL saat
 * menjalankan `npm run dev`. Berguna untuk menguji UI/navigasi ke halaman
 * berikutnya (mis. Digital Twin) SEBELUM backend endpoint parsing siap.
 * Tidak akan pernah aktif di build produksi karena dijaga `import.meta.env.DEV`.
 *
 * HAPUS blok ini (dan pemanggilannya di `runParse`) setelah backend siap.
 */
function shouldUseMockSuccess(): boolean {
  if (!import.meta.env.DEV) return false;
  if (typeof window === 'undefined') return false;
  return new URLSearchParams(window.location.search).get('mock') === 'success';
}

/**
 * Payload dummy dipakai saat mode mock aktif TAPI tidak ada `documentPayload`
 * asli (mis. halaman dibuka langsung lewat address bar/reload, sehingga
 * `location.state` dari React Router kosong). Ini membiarkan `?mock=success`
 * tetap bisa dites tanpa harus datang dari alur navigasi Dashboard -> Parser.
 */
const MOCK_PAYLOAD: DocumentIngestionPayload = {
  templateData: { mock: true },
  workerCvData: { mock: true },
};

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runMockParse(
  onStepUpdate: (id: ParseStepId, status: ParseStepStatus, detail?: string) => void
): Promise<ParseJobResult> {
  for (const stepId of STEP_ORDER) {
    onStepUpdate(stepId, 'active');
    await delay(250);
    onStepUpdate(stepId, 'success');
  }

  return {
    jobId: 'mock-job-id',
    simulationId: 'mock-simulation-id',
    factoryId: 'mock-factory-id',
    workersParsed: 12,
    jobDesksParsed: 5,
    warnings: [],
    factoryStructure: null,
    workerProfile: null,
    compatibilityMatrix: null,
    floorState: null,
  };
}

/**
 * Pengganti `useDocumentParser` khusus untuk DocumentParserPage.
 *
 * Tidak lagi menangani state upload berkas (template/CV) -- halaman
 * sebelumnya sudah menangani upload + ekstraksi dan mengirim hasilnya ke
 * sini sebagai `payload` (JSON). Begitu `payload` tersedia, pipeline tahap
 * 1 - 5 langsung dijalankan secara otomatis saat mount (logika tahap 1 - 5
 * itu sendiri tidak berubah -- lihat `documentParserApi.parseFromPayload`,
 * yang berbagi normalisasi response & pelaporan step yang sama persis
 * dengan jalur upload lama).
 */
export function useDocumentJsonParser(payload: DocumentIngestionPayload | null) {
  // Saat mode mock aktif, izinkan pipeline tetap berjalan meski tidak ada
  // documentPayload asli dari route state (mis. halaman dibuka lewat reload).
  const effectivePayload = payload ?? (shouldUseMockSuccess() ? MOCK_PAYLOAD : null);

  const [steps, setSteps] = useState<ParseStep[]>(INITIAL_STEPS);
  const [jobStatus, setJobStatus] = useState<ParseJobStatus>('idle');
  const [result, setResult] = useState<ParseJobResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);

  // Mencegah pipeline terpicu dua kali (mis. React StrictMode double-mount,
  // atau payload berubah identitas tapi isinya sama).
  const hasRunRef = useRef(false);

  const updateStep = useCallback(
    (id: ParseStepId, status: ParseStepStatus, detail?: string) => {
      setSteps((prev) =>
        prev.map((step) => (step.id === id ? { ...step, status, detail } : step))
      );
    },
    []
  );

  const runParse = useCallback(async (documentPayload: DocumentIngestionPayload) => {
    setJobStatus('running');
    setSteps(INITIAL_STEPS);
    setResult(null);
    setErrorMessage(undefined);

    try {
      const jobResult = shouldUseMockSuccess()
        ? await runMockParse(updateStep)
        : await documentParserApi.parseFromPayload({
            payload: documentPayload,
            onStepUpdate: updateStep,
          });
      setResult(jobResult);
      setJobStatus('success');
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Parsing gagal karena kesalahan tak terduga.'
      );
      setSteps((prev) =>
        prev.map((step) =>
          step.status === 'active' ? { ...step, status: 'error' } : step
        )
      );
      setJobStatus('error');
    }
  }, [updateStep]);

  // Jalankan otomatis begitu payload tersedia saat halaman dimuat.
  useEffect(() => {
    if (!effectivePayload || hasRunRef.current) return;
    hasRunRef.current = true;
    void runParse(effectivePayload);
  }, [effectivePayload, runParse]);

  // Untuk tombol "Coba Lagi" pada kondisi error -- payload yang sama dikirim ulang.
  const retry = useCallback(() => {
    if (!effectivePayload) return;
    void runParse(effectivePayload);
  }, [effectivePayload, runParse]);

  const reset = useCallback(() => {
    hasRunRef.current = false;
    setSteps(INITIAL_STEPS);
    setJobStatus('idle');
    setResult(null);
    setErrorMessage(undefined);
  }, []);

  return {
    steps,
    jobStatus,
    result,
    errorMessage,
    retry,
    reset,
    hasPayload: Boolean(effectivePayload),
  };
}