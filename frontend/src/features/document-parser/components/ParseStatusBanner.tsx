// frontend/src/features/document-parser/components/ParseStatusBanner.tsx
import styles from './ParseStatusBanner.module.css';
import type { ParseJobStatus, ParseStep } from '../types/documentParser.types';

interface ParseStatusBannerProps {
  steps: ParseStep[];
  jobStatus: ParseJobStatus;
  resultSummary?: string;
  errorMessage?: string;
}

const STEP_MARKER: Record<ParseStep['status'], string> = {
  pending: '',
  active: '',
  success: '✓',
  error: '✕',
};

export function ParseStatusBanner({ steps, jobStatus, resultSummary, errorMessage }: ParseStatusBannerProps) {
  if (jobStatus === 'idle') return null;

  return (
    <div className={[styles.banner, styles[jobStatus]].join(' ')}>
      <ol className={styles.steps}>
        {steps.map((step, index) => (
          <li key={step.id} className={[styles.step, styles[step.status]].join(' ')}>
            {index > 0 && <span className={styles.connector} aria-hidden="true" />}
            <span className={styles.stepMarker}>{STEP_MARKER[step.status]}</span>
            <span className={styles.stepLabel}>{step.label}</span>
            {step.detail && <span className={styles.stepDetail}>{step.detail}</span>}
          </li>
        ))}
      </ol>

      {jobStatus === 'success' && resultSummary && <p className={styles.summary}>{resultSummary}</p>}
      {jobStatus === 'error' && (
        <p className={styles.summary}>
          {errorMessage ?? 'Parsing gagal. Periksa langkah yang ditandai di atas, lalu coba lagi.'}
        </p>
      )}
    </div>
  );
}