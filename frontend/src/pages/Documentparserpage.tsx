import { useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ROUTES } from '@/app/router/routes';
import { ParseStatusBanner, type JobBuildStatus } from '@/features/document-parser/components/ParseStatusBanner';
import { ParsedDataInspector } from '@/features/document-parser/components/ParsedDataInspector';
import { useFactoryBuildStatus } from '@/features/document-parser/hooks/useFactoryBuildStatus';
import styles from './DocumentParserPage.module.css';

/**
 * DocumentParserPage kini menjadi "real job-progress view".
 * Halaman ini memonitor status factory dan compatibility job dari API,
 * menggunakan parameter URL (factoryId dan jobId), dan melakukan polling progres.
 */
export function DocumentParserPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Mengambil ID dari URL
  const factoryId = searchParams.get('factoryId');
  const compatibilityJobId = searchParams.get('jobId');

  // Menggunakan hook real-time baru
  const { steps, jobStatus, summary, errorMessage, retry, hasContext } =
    useFactoryBuildStatus(factoryId, compatibilityJobId);

  // Menampilkan ringkasan berdasarkan FactorySummary dari API
  const resultSummary = useMemo(
    () =>
      summary
        ? `${summary.workersCount} pekerja & ${summary.jobDesksCount} job desk tersimpan.`
        : undefined,
    [summary]
  );

  // Navigasi ke Digital Twin menggunakan factoryId murni (tanpa mock=true)
  const handleProceedToDigitalTwin = () => {
    if (factoryId) {
      navigate(`${ROUTES.DIGITAL_TWIN}?factoryId=${encodeURIComponent(factoryId)}`);
      return;
    }
    navigate(ROUTES.DASHBOARD);
  };

  const handleBackToDashboard = () => {
    navigate(ROUTES.DASHBOARD);
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div>
            <span className={styles.eyebrow}>Document Ingestion</span>
            <h1 className={styles.title}>Memproses Factory Baru</h1>
            <p className={styles.subtitle}>
              Data sedang diproses dan divalidasi oleh sistem.
            </p>
          </div>
          {jobStatus !== 'running' && (
            <button type="button" className={styles.resetButton} onClick={handleBackToDashboard}>
              ← Kembali ke Dashboard
            </button>
          )}
        </div>
      </header>

      {!hasContext ? (
        <ParseStatusBanner
          steps={steps}
          jobStatus="error"
          errorMessage="Parameter Factory ID tidak ditemukan di URL. Silakan mulai proses kembali dari Dashboard."
        />
      ) : (
        <ParseStatusBanner
          steps={steps}
          jobStatus={jobStatus as JobBuildStatus}
          resultSummary={resultSummary}
          errorMessage={errorMessage}
        />
      )}

      <section className={styles.actionRow}>
        {!hasContext && (
          <button type="button" className={styles.parseButton} onClick={handleBackToDashboard}>
            Kembali ke Dashboard
          </button>
        )}

        {jobStatus === 'error' && (
          <button type="button" className={styles.parseButton} onClick={retry}>
            Coba Lagi
          </button>
        )}

        {jobStatus === 'success' && (
          <button
            type="button"
            className={`${styles.parseButton} ${styles.successButton}`}
            onClick={handleProceedToDigitalTwin}
          >
            Lanjut ke Digital Twin
          </button>
        )}

        {(jobStatus === 'success' || jobStatus === 'error') && (
          <button type="button" className={styles.resetButton} onClick={handleBackToDashboard}>
            Unggah Berkas Baru
          </button>
        )}
      </section>

      {/* Melempar 'summary' sebagai result ke Inspector */}
      {jobStatus === 'success' && summary && (
        <ParsedDataInspector result={summary} onProceed={handleProceedToDigitalTwin} />
      )}
    </div>
  );
}

export default DocumentParserPage;