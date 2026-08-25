// frontend/src/features/document-parser/components/ParseStatusBanner.tsx
import styles from './ParseStatusBanner.module.css';

// 1. Update the import to pull BuildStep from wherever you define it. 
// (If it's in a types file, update this path accordingly. Here we assume it's exported from the hook).
import type { BuildStep } from '@/features/document-parser/hooks/useFactoryBuildStatus';

// 2. Define the explicit statuses that your new hook uses
export type JobBuildStatus = 'idle' | 'running' | 'success' | 'error';

interface ParseStatusBannerProps {
  steps: BuildStep[];
  jobStatus: JobBuildStatus;
  resultSummary?: string;
  errorMessage?: string;
}

// 3. Update the Record to map against BuildStep's status
const STEP_MARKER: Record<BuildStep['status'], string> = {
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
          {errorMessage ?? 'Proses gagal. Periksa langkah yang ditandai di atas, lalu coba lagi.'}
        </p>
      )}
    </div>
  );
}