import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/router/routes';
import { UploadDropzone } from '@/features/document-parser/components/UploadDropzone';
import { ParseStatusBanner } from '@/features/document-parser/components/ParseStatusBanner';
import { ParsedDataInspector } from '@/features/document-parser/components/ParsedDataInspector';
import { FactoryListSection } from '@/features/document-parser/components/FactoryListSection';
import { useDocumentParser } from '@/features/document-parser/hooks/useDocumentParser';
import { useFactoryList } from '@/features/document-parser/hooks/useFactoryList';
import styles from './DocumentParserPage.module.css';

export function DocumentParserPage() {
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<'list' | 'parse'>('list');

  const { factories, isLoading, error, refetch } = useFactoryList();
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

  // Sinkronkan daftar factory saat parsing sukses
  useEffect(() => {
    if (jobStatus === 'success') {
      refetch();
    }
  }, [jobStatus, refetch]);

  const handleProceedToDigitalTwin = (factoryId?: string) => {
    const targetId = factoryId || result?.factoryId || result?.simulationId || result?.jobId;
    if (targetId) {
      navigate(`${ROUTES.DIGITAL_TWIN}?factory_id=${targetId}`);
    } else {
      navigate(ROUTES.DIGITAL_TWIN);
    }
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div>
            <span className={styles.eyebrow}>Document Ingestion</span>
            <h1 className={styles.title}>
              {viewMode === 'list' ? 'Daftar Factory' : 'Tambah Factory Baru'}
            </h1>
            <p className={styles.subtitle}>
              {viewMode === 'list'
                ? 'Pilih factory terdaftar untuk melihat Digital Twin atau tambahkan baru.'
                : 'Unggah template pabrik dan bundel CV karyawan untuk diparsing terpadu.'}
            </p>
          </div>
          {viewMode === 'list' ? (
            <button
              type="button"
              className={styles.parseButton}
              onClick={() => {
                reset();
                setViewMode('parse');
              }}
            >
              + Add Factory Baru
            </button>
          ) : (
            <button
              type="button"
              className={styles.resetButton}
              onClick={() => setViewMode('list')}
            >
              ← Kembali ke Daftar
            </button>
          )}
        </div>
      </header>

      {viewMode === 'list' ? (
        <FactoryListSection
          factories={factories}
          isLoading={isLoading}
          error={error}
          onSelectFactory={handleProceedToDigitalTwin}
          onAddNewClick={() => {
            reset();
            setViewMode('parse');
          }}
          onRetry={refetch}
        />
      ) : (
        <>
          <section className={styles.uploadGrid}>
            <UploadDropzone
              id="template-upload"
              eyebrow="01 — Template Pabrik"
              title="Template Dokumen Pabrik"
              description="Formulir workflow, aset, dan job desk (PDF, DOCX, MD, TXT, XLSX, XLS, CSV)."
              accept=".pdf,.docx,.md,.markdown,.txt,.xlsx,.xls,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
              acceptLabel="PDF, DOCX, MD, TXT, XLSX, XLS, CSV"
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
              onClick={runParse}
            >
              {jobStatus === 'running' ? 'Memproses Tahap 1 - 5...' : 'Mulai Parsing Terpadu'}
            </button>

            {jobStatus === 'success' && (
              <button
                type="button"
                className={`${styles.parseButton} ${styles.successButton}`}
                onClick={() => setViewMode('list')}
              >
                Selesai & Lihat Daftar Factory
              </button>
            )}

            {(jobStatus === 'success' || jobStatus === 'error') && (
              <button type="button" className={styles.resetButton} onClick={reset}>
                Unggah Berkas Baru
              </button>
            )}
          </section>

          <ParseStatusBanner
            steps={steps}
            jobStatus={jobStatus}
            resultSummary={
              result
                ? `${result.workersParsed} pekerja & ${result.jobDesksParsed} job desk berhasil diparsing.`
                : undefined
            }
            errorMessage={errorMessage}
          />

          {jobStatus === 'success' && result && (
            <ParsedDataInspector
              result={result}
              onProceed={() => handleProceedToDigitalTwin()}
            />
          )}
        </>
      )}
    </div>
  );
}

export default DocumentParserPage;