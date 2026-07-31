import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/router/routes';
import { UploadDropzone } from '@/features/document-parser/components/UploadDropzone';
import { ParseStatusBanner } from '@/features/document-parser/components/ParseStatusBanner';
import { useDocumentParser } from '@/features/document-parser/hooks/Usedocumentparser';
import styles from './DocumentParserPage.module.css';

export function DocumentParserPage() {
  const navigate = useNavigate();

  const {
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
  } = useDocumentParser();

  const resultSummary = result
    ? `${result.workersParsed} pekerja & ${result.jobDesksParsed} job desk berhasil diparsing ke digital twin.`
    : undefined;

  // Handler utama saat tombol parsing diklik
  const handleParse = async () => {
    try {
      await runParse();
      // Jika runParse bersifat synchronous/selesai seketika tanpa jobStatus async,
      // navigasi bisa ditempatkan langsung di sini.
    } catch (error) {
      console.error('Gagal menjalankan parsing:', error);
    }
  };

  // Otomatis berpindah ke Digital Twin saat parsing berhasil diselesaikan
  useEffect(() => {
    if (jobStatus === 'success') {
      const timer = setTimeout(() => {
        navigate(ROUTES.DIGITAL_TWIN);
      }, 1200); // Jeda 1.2 detik agar user sempat melihat status "Selesai" pada banner

      return () => clearTimeout(timer);
    }
  }, [jobStatus, navigate]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Document Ingestion</span>
          <h1 className={styles.title}>Document Parser</h1>
          <p className={styles.subtitle}>
            Unggah template pabrik dan bundel CV karyawan. Keduanya akan disusun ulang menjadi satu digital twin JSON.
          </p>
        </div>
      </header>

      <section className={styles.uploadGrid}>
        <UploadDropzone
          id="template-upload"
          eyebrow="01 — Template Pabrik"
          title="Template PDF"
          description="Formulir workflow, aset, dan job desk sesuai template yang kami sediakan."
          accept="application/pdf"
          acceptLabel="PDF"
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
          accept=".zip,application/zip,application/x-zip-compressed"
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
          {jobStatus === 'running' ? 'Memproses...' : 'Mulai Parsing'}
        </button>

        {jobStatus === 'success' && (
          <button
            type="button"
            className={styles.parseButton}
            onClick={() => navigate(ROUTES.DIGITAL_TWIN)}
          >
            Buka Digital Twin →
          </button>
        )}

        {(jobStatus === 'success' || jobStatus === 'error') && (
          <button type="button" className={styles.resetButton} onClick={reset}>
            Unggah Berkas Baru
          </button>
        )}
      </section>

      <ParseStatusBanner steps={steps} jobStatus={jobStatus} resultSummary={resultSummary} />
    </div>
  );
}

export default DocumentParserPage;