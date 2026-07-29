import { useCallback, useMemo, useState } from 'react';
import { startParseJob } from '../api/Documentparserapi';
import type {
  ParseJobResult,
  ParseJobStatus,
  ParseStep,
  ParseStepId,
  ParseStepStatus,
  UploadSlotState,
} from '../types/documentParser.types';

const TEMPLATE_MIME_TYPES = ['application/pdf'];
const CV_BUNDLE_MIME_TYPES = ['application/zip', 'application/x-zip-compressed', 'application/x-zip'];

const INITIAL_STEPS: ParseStep[] = [
  { id: 'upload', label: 'Unggah Berkas', status: 'pending' },
  { id: 'extract', label: 'Ekstraksi Konten', status: 'pending' },
  { id: 'llm_parse', label: 'Parsing LLM', status: 'pending' },
  { id: 'validate', label: 'Validasi Skema', status: 'pending' },
  { id: 'done', label: 'Selesai', status: 'pending' },
];

function validateFile(file: File, mimeTypes: string[], extension: string): string | undefined {
  const matchesMime = mimeTypes.includes(file.type);
  const matchesExtension = file.name.toLowerCase().endsWith(extension);
  if (!matchesMime && !matchesExtension) {
    return `Format tidak sesuai. Harap unggah berkas ${extension.toUpperCase()}.`;
  }
  return undefined;
}

export function useDocumentParser() {
  const [templateSlot, setTemplateSlot] = useState<UploadSlotState>({ file: null, status: 'idle' });
  const [cvBundleSlot, setCvBundleSlot] = useState<UploadSlotState>({ file: null, status: 'idle' });
  const [steps, setSteps] = useState<ParseStep[]>(INITIAL_STEPS);
  const [jobStatus, setJobStatus] = useState<ParseJobStatus>('idle');
  const [result, setResult] = useState<ParseJobResult | null>(null);

  const selectTemplate = useCallback((file: File) => {
    const errorMessage = validateFile(file, TEMPLATE_MIME_TYPES, '.pdf');
    setTemplateSlot({ file, status: errorMessage ? 'error' : 'selected', errorMessage });
  }, []);

  const selectCvBundle = useCallback((file: File) => {
    const errorMessage = validateFile(file, CV_BUNDLE_MIME_TYPES, '.zip');
    setCvBundleSlot({ file, status: errorMessage ? 'error' : 'selected', errorMessage });
  }, []);

  const clearTemplate = useCallback(() => setTemplateSlot({ file: null, status: 'idle' }), []);
  const clearCvBundle = useCallback(() => setCvBundleSlot({ file: null, status: 'idle' }), []);

  const canParse = useMemo(
    () => templateSlot.status === 'selected' && cvBundleSlot.status === 'selected' && jobStatus !== 'running',
    [templateSlot.status, cvBundleSlot.status, jobStatus]
  );

  const updateStep = useCallback((id: ParseStepId, status: ParseStepStatus, detail?: string) => {
    setSteps((prev) => prev.map((step) => (step.id === id ? { ...step, status, detail } : step)));
  }, []);

  const runParse = useCallback(async () => {
    if (!templateSlot.file || !cvBundleSlot.file) return;

    setJobStatus('running');
    setSteps(INITIAL_STEPS);
    setResult(null);

    try {
      const jobResult = await startParseJob({
        templateFile: templateSlot.file,
        cvBundleFile: cvBundleSlot.file,
        onStepUpdate: updateStep,
      });
      setResult(jobResult);
      setJobStatus('success');
    } catch {
      setSteps((prev) => prev.map((step) => (step.status === 'active' ? { ...step, status: 'error' } : step)));
      setJobStatus('error');
    }
  }, [templateSlot.file, cvBundleSlot.file, updateStep]);

  const reset = useCallback(() => {
    setTemplateSlot({ file: null, status: 'idle' });
    setCvBundleSlot({ file: null, status: 'idle' });
    setSteps(INITIAL_STEPS);
    setJobStatus('idle');
    setResult(null);
  }, []);

  return {
    templateSlot,
    cvBundleSlot,
    steps,
    jobStatus,
    result,
    canParse,
    selectTemplate,
    selectCvBundle,
    clearTemplate,
    clearCvBundle,
    runParse,
    reset,
  };
}