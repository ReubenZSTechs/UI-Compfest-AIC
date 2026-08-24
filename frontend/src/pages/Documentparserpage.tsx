import { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/app/router/routes';
import { ParseStatusBanner } from '@/features/document-parser/components/ParseStatusBanner';
import { ParsedDataInspector } from '@/features/document-parser/components/ParsedDataInspector';
import { useDocumentJsonParser } from '@/features/document-parser/hooks/useDocumentJsonParser';
import type { DocumentParserPageLocationState } from '@/features/document-parser/types/documentParser.types';
import styles from './DocumentParserPage.module.css';

/**
 * DocumentParserPage kini murni sebuah "processor": tidak ada lagi daftar
 * factory maupun langkah pemilihan/penambahan factory untuk melihat Digital
 * Twin. Halaman ini selalu langsung berada dalam mode running/processing,
 * mengolah `documentPayload` (hasil upload + ekstraksi di DashboardPage)
 * yang dibawa lewat route state.
 */
export function DocumentParserPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const documentPayload =
    (location.state as DocumentParserPageLocationState | undefined)?.documentPayload ?? null;

  const { steps, jobStatus, result, errorMessage, retry, hasPayload } =
    useDocumentJsonParser(documentPayload);

  const resultSummary = useMemo(
    () =>
      result
        ? `${result.workersParsed} pekerja & ${result.jobDesksParsed} job desk berhasil diparsing.`
        : undefined,
    [result]
  );

  // --- PEMBARUAN: Penambahan parameter &mock=true atau ?mock=true ---
  const handleProceedToDigitalTwin = () => {
    const targetId = result?.factoryId || result?.simulationId || result?.jobId;
    if (targetId) {
      navigate(`${ROUTES.DIGITAL_TWIN}?factory_id=${targetId}&mock=true`);
    } else {
      navigate(`${ROUTES.DIGITAL_TWIN}?mock=true`);
    }
  };
  // ------------------------------------------------------------------

  // Upload & ekstraksi dokumen dilakukan di DashboardPage; hasilnya (JSON)
  // dikirim ke sini lewat navigate(ROUTES.PARSER, { state: { documentPayload } }).
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
              Data hasil ekstraksi sedang diproses melalui pipeline tahap 1 - 5.
            </p>
          </div>
          {jobStatus !== 'running' && (
            <button type="button" className={styles.resetButton} onClick={handleBackToDashboard}>
              ← Kembali ke Dashboard
            </button>
          )}
        </div>
      </header>

      {!hasPayload ? (
        <ParseStatusBanner
          steps={steps}
          jobStatus="error"
          errorMessage="Tidak ada data hasil ekstraksi yang diterima. Silakan unggah ulang dokumen dari Dashboard."
        />
      ) : (
        <ParseStatusBanner
          steps={steps}
          jobStatus={jobStatus}
          resultSummary={resultSummary}
          errorMessage={errorMessage}
        />
      )}

      <section className={styles.actionRow}>
        {!hasPayload && (
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

      {jobStatus === 'success' && result && (
        <ParsedDataInspector result={result} onProceed={handleProceedToDigitalTwin} />
      )}
    </div>
  );
}

export default DocumentParserPage;