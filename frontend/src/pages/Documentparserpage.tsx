import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/router/routes';
import { UploadDropzone } from '@/features/document-parser/components/UploadDropzone';
import { ParseStatusBanner } from '@/features/document-parser/components/ParseStatusBanner';
import { ParsedDataInspector } from '@/features/document-parser/components/ParsedDataInspector';
import { useDocumentParser } from '@/features/document-parser/hooks/useDocumentParser';
import styles from './DocumentParserPage.module.css';

export function DocumentParserPage() {
  const navigate = useNavigate();

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

  const resultSummary = result
    ? `${result.workersParsed} pekerja & ${result.jobDesksParsed} job desk${
        result.compatibilityMatrix ? ' & matriks kompatibilitas' : ''
      } berhasil diparsing.`
    : undefined;

  const handleParse = async () => {
    try {
      await runParse();
    } catch (error) {
      console.error('Gagal menjalankan parsing:', error);
    }
  };

  // --- PERUBAHAN DI SINI ---
  const handleProceedToDigitalTwin = () => {
    const targetId = result?.simulationId || result?.jobId;
    if (targetId) {
      navigate(`${ROUTES.DIGITAL_TWIN}?simulation_id=${targetId}`);
    } else {
      navigate(ROUTES.DIGITAL_TWIN);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Document Ingestion</span>
          <h1 className={styles.title}>Document Parser</h1>
          <p className={styles.subtitle}>
            Unggah template pabrik dan bundel CV karyawan. Keduanya akan disusun ulang menjadi satu digital twin JSON terpadu.
          </p>
        </div>
      </header>

      <section className={styles.uploadGrid}>
        <UploadDropzone
          id="template-upload"
          eyebrow="01 — Template Pabrik"
          title="Template Dokumen Pabrik"
          description="Formulir workflow, aset, dan job desk (PDF, DOCX, MD, TXT)."
          accept=".pdf,.docx,.md,.markdown,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain"
          acceptLabel="PDF, DOCX, MD, TXT"
          accent="automated"
          file={templateSlot.file}
          errorMessage={templateSlot.errorMessage}
          disabled={jobStatus === 'running'}
          onFileSelect={selectTemplate}
          onClear={clearTemplate}
        />

        <UploadDropzone
          id="cv-bundle-upload"
          eyebrow="02 — Data Karyawan"
          title="Bundel CV (ZIP)"
          description="Kumpulan CV karyawan pabrik dalam satu berkas arsip terkompresi."
          accept=".zip,application/zip,application/x-zip-compressed,application/x-zip"
          acceptLabel="ZIP"
          accent="manual"
          file={cvBundleSlot.file}
          errorMessage={cvBundleSlot.errorMessage}
          disabled={jobStatus === 'running'}
          onFileSelect={selectCvBundle}
          onClear={clearCvBundle}
        />
      </section>

      <section className={styles.actionRow}>
        <button
          type="button"
          className={styles.parseButton}
          disabled={!canParse || jobStatus === 'running'}
          onClick={handleParse}
        >
          {jobStatus === 'running' ? 'Memproses Tahap 1 - 5...' : 'Mulai Parsing Terpadu'}
        </button>

        {(jobStatus === 'success' || jobStatus === 'error') && (
          <button type="button" className={styles.resetButton} onClick={reset}>
            Unggah Berkas Baru
          </button>
        )}
      </section>

      {/* Indikator Status & Pesan Error */}
      <ParseStatusBanner
        steps={steps}
        jobStatus={jobStatus}
        resultSummary={resultSummary}
        errorMessage={errorMessage}
      />

      {/* COMPONENT STREAMLIT-LIKE INSPECTOR & TOMBOL MANUAL NAVIGASI */}
      {jobStatus === 'success' && result && (
        <ParsedDataInspector
          result={result}
          onProceed={handleProceedToDigitalTwin}
        />
      )}
    </div>
  );
}

export default DocumentParserPage;