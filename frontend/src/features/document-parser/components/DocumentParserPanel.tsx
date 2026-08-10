// frontend/src/features/document-parser/components/DocumentParserPanel.tsx

import { useMemo } from 'react';
import { UploadDropzone } from './UploadDropzone';
import { ParseStatusBanner } from './ParseStatusBanner';
import { useDocumentParser } from '../hooks/useDocumentParser';
import styles from './DocumentParserPanel.module.css';

function buildResultSummary(
  result: ReturnType<typeof useDocumentParser>['result']
): string | undefined {
  if (!result) return undefined;

  const workersParsed = result.workersParsed ?? 0;
  const jobDesksParsed = result.jobDesksParsed ?? 0;
  const warnings = result.warnings ?? [];

  const hasMatrix = Boolean(result.compatibilityMatrix);
  const matrixText = hasMatrix ? ' & Matriks Kompatibilitas terbentuk' : '';

  const base = `${workersParsed} pekerja & ${jobDesksParsed} job desk tersimpan${matrixText}.`;

  if (warnings.length === 0) return base;

  return `${base} (${warnings.length} peringatan -- lihat detail di bawah)`;
}

export function DocumentParserPanel() {
  const {
    templateSlot,
    cvBundleSlot,
    steps,
    jobStatus,
    result,
    errorMessage,
    canParse,
    selectTemplate,
    selectCvBundle,
    clearTemplate,
    clearCvBundle,
    runParse,
    reset,
  } = useDocumentParser();

  const resultSummary = useMemo(() => buildResultSummary(result), [result]);
  const isRunning = jobStatus === 'running';

  // Safe fallback untuk list peringatan dan langkah-langkah
  const safeWarnings = result?.warnings ?? [];
  const safeSteps = steps ?? [];

  return (
    <div className={styles.panel}>
      <div className={styles.dropzones}>
        {/* Dropzone Template Pabrik (Tahap 1 & 2) */}
        <UploadDropzone
          id="document-parser-template"
          eyebrow="Tahap 1 & 2"
          title="Template Dokumen Pabrik"
          description="Unggah dokumen struktur pabrik (nama, workflow, aset, job desk)."
          accept=".pdf,.docx,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain"
          acceptLabel="PDF, DOCX, MD, TXT"
          accent="automated"
          file={templateSlot?.file}
          errorMessage={templateSlot?.errorMessage}
          disabled={isRunning}
          onFileSelect={selectTemplate}
          onClear={clearTemplate}
        />

        {/* Dropzone Arsip CV Pekerja (Tahap 4) */}
        <UploadDropzone
          id="document-parser-cv-bundle"
          eyebrow="Tahap 4"
          title="Bundle CV Pekerja"
          description="Unggah satu berkas ZIP berisi seluruh CV/catatan wawancara pekerja."
          accept=".zip,application/zip,application/x-zip-compressed,application/x-zip"
          acceptLabel="ZIP"
          accent="manual"
          file={cvBundleSlot?.file}
          errorMessage={cvBundleSlot?.errorMessage}
          disabled={isRunning}
          onFileSelect={selectCvBundle}
          onClear={clearCvBundle}
        />
      </div>

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.primaryButton}
          disabled={!canParse}
          onClick={runParse}
        >
          {isRunning ? 'Memproses Tahap 1 - 5...' : 'Jalankan Parsing Terpadu'}
        </button>

        {jobStatus !== 'idle' && (
          <button
            type="button"
            className={styles.secondaryButton}
            disabled={isRunning}
            onClick={reset}
          >
            Reset
          </button>
        )}
      </div>

      {/* Indikator Progres Steps & Banner Error/Sukses */}
      <ParseStatusBanner
        steps={safeSteps}
        jobStatus={jobStatus}
        resultSummary={resultSummary}
        errorMessage={errorMessage}
      />

      {/* Rincian Peringatan Non-Fatal */}
      {jobStatus === 'success' && safeWarnings.length > 0 && (
        <ul className={styles.warningList}>
          {safeWarnings.map((warning, index) => (
            <li key={`${warning}-${index}`}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}